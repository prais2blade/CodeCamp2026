from decimal import Decimal
import datetime
import tempfile
import csv
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db.models import Sum, Count, Q
from django.core.serializers.json import DjangoJSONEncoder
from weasyprint import HTML

from apps.accounts.decorators import role_required
from apps.courses.models import Course
from .models import Payment, Receipt


@login_required
@role_required('hod')
def manage_payments(request):
    """Payment Approvals and Tuition Management Console."""
    status_filter = request.GET.get('status', 'all')
    course_filter = request.GET.get('course_id')
    query = request.GET.get('q', '').strip()

    payments_qs = Payment.objects.select_related('student', 'course', 'batch', 'verified_by').prefetch_related('receipts').order_by('-payment_date')

    if status_filter == 'pending':
        payments_qs = payments_qs.filter(is_approved=False)
    elif status_filter == 'approved':
        payments_qs = payments_qs.filter(is_approved=True)

    if course_filter:
        payments_qs = payments_qs.filter(course_id=course_filter)

    if query:
        payments_qs = payments_qs.filter(
            Q(student__username__icontains=query) |
            Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query) |
            Q(student__email__icontains=query) |
            Q(payment_ref__icontains=query)
        )

    # Metrics
    all_p = Payment.objects.all()
    pending_count = all_p.filter(is_approved=False).count()
    approved_count = all_p.filter(is_approved=True).count()
    total_collected = all_p.filter(is_approved=True).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    total_discounts = all_p.aggregate(Sum('discount'))['discount__sum'] or Decimal('0.00')
    total_expected = all_p.aggregate(Sum('amount_due'))['amount_due__sum'] or Decimal('0.00')
    net_expected = max(Decimal('0.00'), total_expected - total_discounts)
    outstanding_balance = max(Decimal('0.00'), net_expected - total_collected)

    all_courses = Course.objects.all().order_by('name')
    from apps.scheduling.models import Batch
    all_batches = Batch.objects.all().select_related('course').order_by('course__name', 'name')

    context = {
        'payments': payments_qs,
        'status_filter': status_filter,
        'course_filter': course_filter,
        'query': query,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'total_collected': total_collected,
        'total_discounts': total_discounts,
        'net_expected': net_expected,
        'outstanding_balance': outstanding_balance,
        'all_courses': all_courses,
        'all_batches': all_batches,
    }
    return render(request, 'payments/manage_payments.html', context)


@login_required
@role_required('hod')
def approve_payment(request, payment_id):
    """Approves a payment, verifies/corrects amount, applies discount, and generates official receipt."""
    payment = get_object_or_404(Payment, id=payment_id)
    if request.method == 'POST':
        amount_paid_raw = request.POST.get('amount_paid')
        discount_raw = request.POST.get('discount', '0')
        discount_reason = request.POST.get('discount_reason', '').strip()
        notes = request.POST.get('notes', '').strip()
        issue_receipt = request.POST.get('issue_receipt') == 'on'

        try:
            if amount_paid_raw is not None and amount_paid_raw != '':
                payment.amount_paid = Decimal(amount_paid_raw)
            if discount_raw:
                payment.discount = Decimal(discount_raw)
        except Exception as e:
            messages.error(request, f"Invalid monetary values provided: {e}")
            return redirect('manage_payments')

        if discount_reason:
            payment.discount_reason = discount_reason
        if notes:
            payment.notes = notes

        payment.is_approved = True
        payment.approved_at = timezone.now()
        payment.verified_by = request.user
        payment.update_status()

        receipt_ref = None
        if issue_receipt and payment.amount_paid > 0:
            receipt = Receipt.objects.create(payment=payment, amount=payment.amount_paid)
            receipt_ref = str(receipt.reference)[:8].upper()

        success_msg = f"Payment for {payment.student.get_full_name() or payment.student.username} approved!"
        if receipt_ref:
            success_msg += f" Official Receipt #{receipt_ref} issued."
        messages.success(request, success_msg)

        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'manage_payments'
        return redirect(next_url)

    return redirect('manage_payments')


@login_required
@role_required('hod')
def bulk_apply_discount(request):
    """Applies discounts or agreed custom pricing to a cohort or multiple selected students in 1 click."""
    if request.method == 'POST':
        mode = request.POST.get('mode', 'students')  # 'cohort' or 'students'
        discount_type = request.POST.get('discount_type', 'discount_amount')  # 'discount_amount' or 'agreed_fee'
        amount_raw = request.POST.get('amount', '0').strip()
        reason = request.POST.get('reason', '').strip()

        try:
            val = Decimal(amount_raw)
            if val < 0:
                raise ValueError("Amount cannot be negative.")
        except Exception:
            messages.error(request, "Please enter a valid numeric amount.")
            return redirect(request.META.get('HTTP_REFERER') or 'manage_payments')

        target_payments = Payment.objects.none()

        if mode == 'cohort':
            batch_id = request.POST.get('batch_id')
            from apps.scheduling.models import Batch
            batch = get_object_or_404(Batch, id=batch_id)
            target_payments = Payment.objects.filter(Q(batch=batch) | Q(student__profile__batch=batch))
        else:
            student_ids = request.POST.getlist('student_ids')
            if not student_ids:
                raw_ids = request.POST.get('student_ids_csv', '')
                if raw_ids:
                    student_ids = [x.strip() for x in raw_ids.split(',') if x.strip()]

            if not student_ids:
                messages.warning(request, "No students were selected for discount.")
                return redirect(request.META.get('HTTP_REFERER') or 'manage_payments')

            target_payments = Payment.objects.filter(
                Q(id__in=student_ids) | Q(student_id__in=student_ids) | Q(student__profile__id__in=student_ids)
            )

        updated_count = 0
        for p in target_payments:
            if discount_type == 'agreed_fee':
                computed_discount = max(Decimal('0.00'), p.amount_due - val)
            else:
                computed_discount = min(p.amount_due, val)

            p.discount = computed_discount
            if reason:
                p.discount_reason = reason
            p.update_status()
            p.calculate_monthly_payment()
            updated_count += 1

        messages.success(
            request,
            f"Successfully updated tuition pricing for {updated_count} student record(s)! Expected payments & balances recalculated."
        )
        return redirect(request.META.get('HTTP_REFERER') or 'manage_payments')

    return redirect('manage_payments')


@login_required
@role_required('hod')
def update_payment_status(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', '0'))
        discount_raw = request.POST.get('discount')
        if discount_raw:
            try:
                payment.discount = Decimal(discount_raw)
            except Exception:
                pass

        payment.amount_paid += amount
        payment.payment_date = timezone.now()
        payment.is_approved = True
        payment.verified_by = request.user
        payment.update_status()
        payment.save()
        Receipt.objects.create(payment=payment, amount=amount)

        messages.success(request, f"₦{amount:,.2f} added for {payment.student.username}. New balance: ₦{payment.remaining_balance():,.2f}.")
        return redirect('manage_payments')

    return render(request, 'payments/update_payment.html', {'payment': payment})


@login_required
@role_required('student')
def student_payments(request):
    payments = Payment.objects.filter(student=request.user).order_by('-payment_date')
    due_payment = payments.first().monthly_payment if payments.exists() else None
    return render(request, 'payments/student_payments.html', {
        'payments': payments,
        'due_payment': due_payment
    })


@login_required
def view_receipt(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    payment = receipt.payment
    html_string = render_to_string('payments/receipt_template.html', {'receipt': receipt, 'payment': payment})

    if 'download' in request.GET:
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Receipt_{receipt.reference}.pdf"'
        html = HTML(string=html_string)
        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            html.write_pdf(target=tmp.name)
            tmp.seek(0)
            response.write(tmp.read())
        return response

    return HttpResponse(html_string)


@login_required
@role_required('hod')
def export_monthly_trend_csv(request):
    from .models import Payment
    payments = Payment.objects.all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="monthly_revenue_trend.csv"'

    writer = csv.writer(response)
    writer.writerow(['Month', 'Total Paid (₦)', 'Total Due (₦)'])

    today = timezone.now().date().replace(day=1)
    months = [(today.year, today.month)]
    for _ in range(11):
        y, m = months[-1]
        m -= 1
        if m == 0:
            m = 12
            y -= 1
        months.append((y, m))
    months.reverse()

    for y, m in months:
        start = datetime.date(y, m, 1)
        end = datetime.date(y + (m == 12), (m % 12) + 1, 1)
        month_paid = payments.filter(payment_date__date__gte=start, payment_date__date__lt=end).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        month_due = payments.filter(payment_date__date__gte=start, payment_date__date__lt=end).aggregate(Sum('amount_due'))['amount_due__sum'] or 0
        writer.writerow([start.strftime('%b %Y'), month_paid, month_due])

    return response


@login_required
@role_required('hod')
def revenue_dashboard(request):
    from .models import Payment
    from apps.courses.models import Course

    payments = Payment.objects.select_related('course', 'batch', 'student')
    total_income = payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    total_due = payments.aggregate(Sum('amount_due'))['amount_due__sum'] or 0
    total_balance = total_due - total_income

    stats = {
        'total_income': total_income,
        'total_due': total_due,
        'total_balance': total_balance,
        'paid_count': payments.filter(status='paid').count(),
        'partial_count': payments.filter(status='partial').count(),
        'pending_count': payments.filter(status='pending').count(),
    }

    # --- Course revenue (bar chart) ---
    course_data = []
    for course in Course.objects.all():
        total_paid = payments.filter(course=course).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        total_due_c = payments.filter(course=course).aggregate(Sum('amount_due'))['amount_due__sum'] or 0
        course_data.append({
            'course': course.name,
            'paid': float(total_paid),
            'due': float(total_due_c),
        })

    # --- Monthly trend (Paid vs Due) ---
    def last_n_months(n=12):
        today = timezone.now().date().replace(day=1)
        year, month = today.year, today.month
        months = []
        for _ in range(n):
            months.append((year, month))
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        return months[::-1]

    trend_labels, paid_data, due_data = [], [], []
    for y, m in last_n_months(12):
        start = datetime.date(y, m, 1)
        end = datetime.date(y + (m == 12), (m % 12) + 1, 1)
        month_paid = payments.filter(payment_date__date__gte=start, payment_date__date__lt=end).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        month_due = payments.filter(payment_date__date__gte=start, payment_date__date__lt=end).aggregate(Sum('amount_due'))['amount_due__sum'] or 0
        trend_labels.append(start.strftime('%b %Y'))
        paid_data.append(float(month_paid))
        due_data.append(float(month_due))

    chart_data = {
        'labels': [c['course'] for c in course_data],
        'paid': [c['paid'] for c in course_data],
        'due': [c['due'] for c in course_data],
        'status_labels': ['Paid', 'Partial', 'Pending'],
        'status_counts': [
            stats['paid_count'],
            stats['partial_count'],
            stats['pending_count']
        ],
        'trend_labels': trend_labels,
        'paid_data': paid_data,
        'due_data': due_data,
    }

    return render(request, 'payments/revenue_dashboard.html', {
        'stats': stats,
        'chart_data': json.dumps(chart_data, cls=DjangoJSONEncoder),
        'course_stats': course_data,
    })


@login_required
@role_required('hod')
def export_revenue_csv(request):
    from .models import Payment

    payments = Payment.objects.select_related('course', 'batch', 'student').all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="revenue_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Student', 'Course', 'Batch', 'Status', 'Amount Due', 'Amount Paid', 'Balance'])

    for p in payments:
        writer.writerow([
            p.student.username,
            p.course.name if p.course else '-',
            p.batch.name if p.batch else '-',
            p.status,
            p.amount_due,
            p.amount_paid,
            p.remaining_balance()
        ])

    return response


@login_required
@role_required('student')
def receipt_center(request):
    from .models import Receipt

    receipts = (
        Receipt.objects
        .filter(payment__student=request.user)
        .select_related('payment', 'payment__course', 'payment__batch')
        .order_by('-issued_date')
    )

    return render(request, 'payments/receipt_center.html', {'receipts': receipts})
