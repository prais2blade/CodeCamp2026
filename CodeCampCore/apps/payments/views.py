from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.accounts.decorators import role_required
from .models import Payment, Receipt
from decimal import Decimal
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
import tempfile
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
import csv
import json
from django.core.serializers.json import DjangoJSONEncoder
import datetime
from apps.courses.models import Course

@login_required
@role_required('hod')
def manage_payments(request):
    payments = Payment.objects.select_related('student', 'course', 'batch').order_by('-payment_date')
    return render(request, 'payments/manage_payments.html', {'payments': payments})


@login_required
@role_required('hod')
def update_payment_status(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount'))
        
        # Enforce minimum monthly payment rule
        if amount < payment.monthly_payment:
            messages.error(request, f"Payment must be at least ₦{payment.monthly_payment} (monthly minimum).")
            return redirect('update_payment', payment_id=payment_id)

        payment.amount_paid += amount
        payment.payment_date = timezone.now()
        payment.update_status()
        payment.verified_by = request.user
        payment.save()
        Receipt.objects.create(payment=payment, amount=amount)

        messages.success(request, f"₦{amount} added for {payment.student.username}. New balance: ₦{payment.remaining_balance()}.")
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
    


def _last_n_months(n=12, end_date=None):
    """Return a list of (year, month) tuples for the last `n` months ending at end_date (inclusive)."""
    if end_date is None:
        end_date = timezone.now().date().replace(day=1)
    year = end_date.year
    month = end_date.month
    months = []
    for _ in range(n):
        months.append((year, month))
        # decrement month
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    months.reverse()  # oldest -> newest
    return months


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
