from decimal import Decimal
import datetime
import tempfile
import csv
import json
import io

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db.models import Sum, Count, Q
from django.core.serializers.json import DjangoJSONEncoder
from weasyprint import HTML

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from apps.accounts.decorators import role_required
from apps.courses.models import Course
from apps.scheduling.models import Batch
from .models import Payment, Receipt


# ==============================================================================
# 1. ACCOUNTANT EXECUTIVE DASHBOARD
# ==============================================================================

@login_required
@role_required(['accountant', 'hod'])
def accountant_dashboard(request):
    """
    Financial Command Center for Academy Accountants & HODs.
    Provides real-time visibility into collections, debtors, revenue, and approval queues.
    """
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    all_payments = Payment.objects.select_related('student', 'course', 'batch', 'verified_by').prefetch_related('receipts')

    # Financial KPIs
    total_gross = all_payments.aggregate(Sum('amount_due'))['amount_due__sum'] or Decimal('0.00')
    total_discounts = all_payments.aggregate(Sum('discount'))['discount__sum'] or Decimal('0.00')
    net_expected = max(Decimal('0.00'), total_gross - total_discounts)
    total_collected = all_payments.filter(is_approved=True).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    total_outstanding = max(Decimal('0.00'), net_expected - total_collected)

    # Periodic Cash Flow
    this_month_collection = all_payments.filter(
        is_approved=True,
        payment_date__gte=month_start
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')

    today_collection = all_payments.filter(
        is_approved=True,
        payment_date__gte=today_start
    ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')

    # Student & Status Counts
    pending_approvals_count = all_payments.filter(is_approved=False).count()
    approved_count = all_payments.filter(is_approved=True).count()
    paid_count = all_payments.filter(status='paid').count()
    partial_count = all_payments.filter(status='partial').count()
    unpaid_count = all_payments.filter(status='pending').count()
    debtors_count = all_payments.filter(Q(status='partial') | (Q(status='pending') & Q(amount_due__gt=0))).count()

    # Recent Transactions & Approvals
    recent_transactions = all_payments.order_by('-payment_date')[:8]
    pending_approvals = all_payments.filter(is_approved=False).order_by('-payment_date')[:6]

    # Course Revenue Performance
    course_stats = []
    for course in Course.objects.all():
        c_payments = all_payments.filter(course=course)
        c_due = c_payments.aggregate(Sum('amount_due'))['amount_due__sum'] or Decimal('0.00')
        c_disc = c_payments.aggregate(Sum('discount'))['discount__sum'] or Decimal('0.00')
        c_net = max(Decimal('0.00'), c_due - c_disc)
        c_paid = c_payments.filter(is_approved=True).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
        c_bal = max(Decimal('0.00'), c_net - c_paid)
        course_stats.append({
            'course': course.name,
            'students_count': c_payments.count(),
            'net_due': float(c_net),
            'paid': float(c_paid),
            'balance': float(c_bal),
            'collection_rate': round((float(c_paid) / float(c_net) * 100), 1) if c_net > 0 else 0
        })

    # Monthly Trend (Past 6 Months)
    def last_n_months(n=6):
        cur = timezone.now().date().replace(day=1)
        months = []
        for _ in range(n):
            months.append((cur.year, cur.month))
            cur = (cur.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        return months[::-1]

    trend_labels, trend_collected = [], []
    for y, m in last_n_months(6):
        start = datetime.date(y, m, 1)
        end = datetime.date(y + (m == 12), (m % 12) + 1, 1)
        m_paid = all_payments.filter(
            is_approved=True,
            payment_date__date__gte=start,
            payment_date__date__lt=end
        ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
        trend_labels.append(start.strftime('%b %Y'))
        trend_collected.append(float(m_paid))

    context = {
        'total_gross': total_gross,
        'total_discounts': total_discounts,
        'net_expected': net_expected,
        'total_collected': total_collected,
        'total_outstanding': total_outstanding,
        'this_month_collection': this_month_collection,
        'today_collection': today_collection,
        'pending_approvals_count': pending_approvals_count,
        'approved_count': approved_count,
        'paid_count': paid_count,
        'partial_count': partial_count,
        'unpaid_count': unpaid_count,
        'debtors_count': debtors_count,
        'recent_transactions': recent_transactions,
        'pending_approvals': pending_approvals,
        'course_stats': course_stats,
        'chart_labels': json.dumps(trend_labels),
        'chart_collected': json.dumps(trend_collected),
        'all_courses': Course.objects.all().order_by('name'),
        'all_batches': Batch.objects.all().select_related('course').order_by('course__name', 'name'),
    }
    return render(request, 'payments/accountant_dashboard.html', context)


# ==============================================================================
# 2. STUDENT TUITION & DEBTORS LEDGER ("Who paid & How much they owe")
# ==============================================================================

@login_required
@role_required(['accountant', 'hod'])
def debtors_ledger(request):
    """
    Dedicated Tuition Ledger and Debtors Tracking.
    Allows accountants to monitor outstanding balances, payment completions, and log payments.
    """
    status_filter = request.GET.get('status', 'all')  # all, debtors, partial, unpaid, paid
    course_filter = request.GET.get('course_id')
    batch_filter = request.GET.get('batch_id')
    query = request.GET.get('q', '').strip()

    payments_qs = Payment.objects.select_related(
        'student', 'student__profile', 'course', 'batch', 'verified_by'
    ).prefetch_related('receipts').order_by('-payment_date')

    # Apply Filters
    if status_filter == 'debtors':
        # Either partially paid or pending with tuition due
        payments_qs = payments_qs.filter(Q(status='partial') | (Q(status='pending') & Q(amount_due__gt=0)))
    elif status_filter == 'partial':
        payments_qs = payments_qs.filter(status='partial')
    elif status_filter == 'unpaid':
        payments_qs = payments_qs.filter(status='pending', amount_paid=0)
    elif status_filter == 'paid':
        payments_qs = payments_qs.filter(status='paid')

    if course_filter:
        payments_qs = payments_qs.filter(course_id=course_filter)
    if batch_filter:
        payments_qs = payments_qs.filter(batch_id=batch_filter)

    if query:
        payments_qs = payments_qs.filter(
            Q(student__username__icontains=query) |
            Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query) |
            Q(student__email__icontains=query) |
            Q(student__profile__phone__icontains=query) |
            Q(payment_ref__icontains=query)
        )

    # Filtered aggregation summary
    filtered_gross = payments_qs.aggregate(Sum('amount_due'))['amount_due__sum'] or Decimal('0.00')
    filtered_disc = payments_qs.aggregate(Sum('discount'))['discount__sum'] or Decimal('0.00')
    filtered_net = max(Decimal('0.00'), filtered_gross - filtered_disc)
    filtered_collected = payments_qs.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    filtered_outstanding = max(Decimal('0.00'), filtered_net - filtered_collected)

    context = {
        'payments': payments_qs,
        'status_filter': status_filter,
        'course_filter': course_filter,
        'batch_filter': batch_filter,
        'query': query,
        'filtered_count': payments_qs.count(),
        'filtered_gross': filtered_gross,
        'filtered_disc': filtered_disc,
        'filtered_net': filtered_net,
        'filtered_collected': filtered_collected,
        'filtered_outstanding': filtered_outstanding,
        'all_courses': Course.objects.all().order_by('name'),
        'all_batches': Batch.objects.all().select_related('course').order_by('course__name', 'name'),
    }
    return render(request, 'payments/debtors_ledger.html', context)


# ==============================================================================
# 3. DIRECT PAYMENT RECORDING (Cash, Bank Transfer, POS, Installments)
# ==============================================================================

@login_required
@role_required(['accountant', 'hod'])
def record_payment(request):
    """
    Accountant-initiated payment entry for manual bank deposits, cash, POS, or installments.
    Instantly updates balance, approves transaction, and auto-issues an official receipt.
    """
    if request.method == 'POST':
        payment_id = request.POST.get('payment_id')
        student_id = request.POST.get('student_id')
        amount_raw = request.POST.get('amount', '').strip()
        discount_raw = request.POST.get('discount', '').strip()
        discount_reason = request.POST.get('discount_reason', '').strip()
        payment_method = request.POST.get('payment_method', 'Bank Transfer').strip()
        notes = request.POST.get('notes', '').strip()
        issue_receipt = request.POST.get('issue_receipt', 'on') in ['on', 'true', 'True', '1']

        try:
            amount = Decimal(amount_raw)
            if amount <= Decimal('0.00'):
                raise ValueError("Payment amount must be greater than zero.")
        except Exception as e:
            messages.error(request, f"Invalid payment amount: {e}")
            return redirect(request.META.get('HTTP_REFERER') or 'debtors_ledger')

        payment = None
        if payment_id:
            payment = get_object_or_404(Payment, id=payment_id)
        elif student_id:
            student = get_object_or_404(User, id=student_id)
            payment = Payment.objects.filter(student=student).first()
            if not payment:
                # If no payment record exists yet, create one using student's course fee
                course = getattr(student.profile, 'course', None)
                course_fee = course.fee if course and hasattr(course, 'fee') else Decimal('50000.00')
                payment = Payment.objects.create(
                    student=student,
                    course=course,
                    batch=getattr(student.profile, 'batch', None),
                    amount_due=course_fee,
                    amount_paid=Decimal('0.00')
                )

        if not payment:
            messages.error(request, "No valid tuition account found for this student.")
            return redirect(request.META.get('HTTP_REFERER') or 'debtors_ledger')

        # Apply discount adjustment if provided
        if discount_raw:
            try:
                discount_val = Decimal(discount_raw)
                payment.discount = discount_val
                if discount_reason:
                    payment.discount_reason = discount_reason
            except Exception:
                pass

        # Credit the account
        payment.amount_paid += amount
        payment.payment_date = timezone.now()
        payment.is_approved = True
        payment.approved_at = timezone.now()
        payment.verified_by = request.user

        # Audit notes
        timestamp_str = timezone.now().strftime('%d-%b-%Y %H:%M')
        audit_entry = f"[{timestamp_str}] Received ₦{amount:,.2f} via {payment_method} by {request.user.username}."
        if notes:
            audit_entry += f" Memo/Ref: {notes}"
        payment.notes = f"{payment.notes}\n{audit_entry}".strip() if payment.notes else audit_entry

        payment.update_status()
        payment.save()

        # Issue Receipt
        receipt_ref = None
        if issue_receipt:
            receipt = Receipt.objects.create(payment=payment, amount=amount)
            receipt_ref = str(receipt.reference)[:8].upper()

        success_msg = f"Recorded payment of ₦{amount:,.2f} for {payment.student.get_full_name() or payment.student.username}. New Balance: ₦{payment.remaining_balance():,.2f}."
        if receipt_ref:
            success_msg += f" Official Receipt #{receipt_ref} generated."
        messages.success(request, success_msg)

        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'debtors_ledger'
        return redirect(next_url)

    return redirect('debtors_ledger')


# ==============================================================================
# 4. EXCEL EXPORT FOR BANK & TUITION RECONCILIATION (.xlsx)
# ==============================================================================

@login_required
@role_required(['accountant', 'hod'])
def export_reconciliation_excel(request):
    """
    Generates a formatted Microsoft Excel (.xlsx) reconciliation workbook
    with financial audit columns, totals formulas, and status indicators.
    """
    status_filter = request.GET.get('status', 'all')
    course_filter = request.GET.get('course_id')
    batch_filter = request.GET.get('batch_id')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    query = request.GET.get('q', '').strip()

    payments_qs = Payment.objects.select_related(
        'student', 'student__profile', 'course', 'batch', 'verified_by'
    ).prefetch_related('receipts').order_by('-payment_date')

    if status_filter == 'debtors':
        payments_qs = payments_qs.filter(Q(status='partial') | (Q(status='pending') & Q(amount_due__gt=0)))
    elif status_filter == 'partial':
        payments_qs = payments_qs.filter(status='partial')
    elif status_filter == 'unpaid':
        payments_qs = payments_qs.filter(status='pending', amount_paid=0)
    elif status_filter == 'paid':
        payments_qs = payments_qs.filter(status='paid')

    if course_filter:
        payments_qs = payments_qs.filter(course_id=course_filter)
    if batch_filter:
        payments_qs = payments_qs.filter(batch_id=batch_filter)

    if date_from:
        try:
            d_from = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            payments_qs = payments_qs.filter(payment_date__date__gte=d_from)
        except ValueError:
            pass

    if date_to:
        try:
            d_to = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            payments_qs = payments_qs.filter(payment_date__date__lte=d_to)
        except ValueError:
            pass

    if query:
        payments_qs = payments_qs.filter(
            Q(student__username__icontains=query) |
            Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query) |
            Q(student__email__icontains=query) |
            Q(payment_ref__icontains=query)
        )

    # Create Workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reconciliation"
    ws.views.sheetView[0].showGridLines = True

    # Palette & Styles
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=16, bold=True, color="1E3A8A")
    meta_font = Font(name="Calibri", size=10, italic=True, color="475569")
    total_font = Font(name="Calibri", size=11, bold=True, color="000000")
    total_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )
    total_border = Border(
        top=Side(style='thin', color='000000'),
        bottom=Side(style='double', color='000000')
    )

    # 1. Title Banner
    ws.merge_cells("A1:R1")
    ws["A1"] = "CODECAMP CORE ACADEMY - FINANCIAL & TUITION RECONCILIATION"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    # 2. Metadata Banner
    gen_time = timezone.now().strftime('%d-%b-%Y %I:%M %p')
    gen_by = request.user.get_full_name() or request.user.username
    ws.merge_cells("A2:R2")
    ws["A2"] = f"Report Date: {gen_time}  |  Generated By: {gen_by}  |  Total Records: {payments_qs.count()}"
    ws["A2"].font = meta_font
    ws.row_dimensions[2].height = 18

    # Blank Row 3
    ws.row_dimensions[3].height = 8

    # 3. Headers (Row 4)
    headers = [
        "S/N", "Payment Ref", "Date", "Student Name", "Username", "Email", "Phone",
        "Course", "Batch/Cohort", "Gross Fee (₦)", "Discount (₦)", "Discount Reason",
        "Net Due (₦)", "Amount Paid (₦)", "Balance Owed (₦)", "Payment Status",
        "Approval", "Verified By", "Receipts", "Audit Remarks / Notes"
    ]
    ws.append([])  # Spacer for row 3
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center" if col_idx in [1, 3, 16, 17] else "left", vertical="center")
    ws.row_dimensions[4].height = 25

    # 4. Data Rows
    start_row = 5
    for idx, p in enumerate(payments_qs, 1):
        row_num = start_row + idx - 1
        phone = getattr(getattr(p.student, 'profile', None), 'phone', '') or ''
        course_name = p.course.name if p.course else 'N/A'
        batch_name = p.batch.name if p.batch else 'N/A'
        verifier_name = p.verified_by.get_full_name() or p.verified_by.username if p.verified_by else 'Unverified'
        receipt_refs = ", ".join([str(r.reference)[:8].upper() for r in p.receipts.all()]) or "None"

        ws.cell(row=row_num, column=1, value=idx).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=2, value=str(p.payment_ref)[:8].upper())
        ws.cell(row=row_num, column=3, value=p.payment_date.strftime('%Y-%m-%d %H:%M') if p.payment_date else '')
        ws.cell(row=row_num, column=4, value=p.student.get_full_name() or p.student.username)
        ws.cell(row=row_num, column=5, value=p.student.username)
        ws.cell(row=row_num, column=6, value=p.student.email)
        ws.cell(row=row_num, column=7, value=phone)
        ws.cell(row=row_num, column=8, value=course_name)
        ws.cell(row=row_num, column=9, value=batch_name)

        # Monetary Columns
        c_gross = ws.cell(row=row_num, column=10, value=float(p.amount_due))
        c_gross.number_format = '#,##0.00'
        c_gross.alignment = Alignment(horizontal="right")

        c_disc = ws.cell(row=row_num, column=11, value=float(p.discount))
        c_disc.number_format = '#,##0.00'
        c_disc.alignment = Alignment(horizontal="right")

        ws.cell(row=row_num, column=12, value=p.discount_reason or '')

        c_net = ws.cell(row=row_num, column=13, value=float(p.net_amount_due))
        c_net.number_format = '#,##0.00'
        c_net.alignment = Alignment(horizontal="right")

        c_paid = ws.cell(row=row_num, column=14, value=float(p.amount_paid))
        c_paid.number_format = '#,##0.00'
        c_paid.alignment = Alignment(horizontal="right")

        c_bal = ws.cell(row=row_num, column=15, value=float(p.remaining_balance()))
        c_bal.number_format = '#,##0.00'
        c_bal.alignment = Alignment(horizontal="right")

        # Statuses
        status_cell = ws.cell(row=row_num, column=16, value=p.status.upper())
        status_cell.alignment = Alignment(horizontal="center")
        if p.status == 'paid':
            status_cell.fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")  # Light green
        elif p.status == 'partial':
            status_cell.fill = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")  # Light yellow
        else:
            status_cell.fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")  # Light red

        app_cell = ws.cell(row=row_num, column=17, value="APPROVED" if p.is_approved else "PENDING")
        app_cell.alignment = Alignment(horizontal="center")

        ws.cell(row=row_num, column=18, value=verifier_name)
        ws.cell(row=row_num, column=19, value=receipt_refs)
        ws.cell(row=row_num, column=20, value=p.notes or '')

        # Apply borders to row
        for c in range(1, 21):
            ws.cell(row=row_num, column=c).border = thin_border

        ws.row_dimensions[row_num].height = 20

    # 5. Totals Row
    last_data_row = start_row + len(payments_qs) - 1
    total_row = last_data_row + 1

    if payments_qs.exists():
        ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=9)
        total_label = ws.cell(row=total_row, column=1, value="TOTAL FINANCIAL SUMMARY")
        total_label.font = total_font
        total_label.alignment = Alignment(horizontal="right", vertical="center")

        # Formulas for sums
        gross_sum = ws.cell(row=total_row, column=10, value=f"=SUM(J{start_row}:J{last_data_row})")
        gross_sum.number_format = '#,##0.00'
        gross_sum.font = total_font

        disc_sum = ws.cell(row=total_row, column=11, value=f"=SUM(K{start_row}:K{last_data_row})")
        disc_sum.number_format = '#,##0.00'
        disc_sum.font = total_font

        ws.cell(row=total_row, column=12, value="")

        net_sum = ws.cell(row=total_row, column=13, value=f"=SUM(M{start_row}:M{last_data_row})")
        net_sum.number_format = '#,##0.00'
        net_sum.font = total_font

        paid_sum = ws.cell(row=total_row, column=14, value=f"=SUM(N{start_row}:N{last_data_row})")
        paid_sum.number_format = '#,##0.00'
        paid_sum.font = total_font

        bal_sum = ws.cell(row=total_row, column=15, value=f"=SUM(O{start_row}:O{last_data_row})")
        bal_sum.number_format = '#,##0.00'
        bal_sum.font = total_font

        for c in range(1, 21):
            cell = ws.cell(row=total_row, column=c)
            cell.fill = total_fill
            cell.border = total_border
        ws.row_dimensions[total_row].height = 24

    # 6. Auto-fit column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            # Skip title / meta rows from calculation
            if cell.row in [1, 2]:
                continue
            val_str = str(cell.value or '')
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # Specific tweaks
    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 24
    ws.column_dimensions['E'].width = 16
    ws.column_dimensions['F'].width = 26
    ws.column_dimensions['T'].width = 30

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"CodeCamp_Reconciliation_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ==============================================================================
# 5. ACCOUNTANT RECEIPT REPOSITORY
# ==============================================================================

@login_required
@role_required(['accountant', 'hod'])
def accountant_receipts(request):
    """
    Searchable audit repository of all issued official receipts.
    Accountants can search by receipt reference, student, or filter by date.
    """
    query = request.GET.get('q', '').strip()
    receipts_qs = Receipt.objects.select_related(
        'payment', 'payment__student', 'payment__course', 'payment__batch', 'payment__verified_by'
    ).order_by('-issued_date')

    if query:
        receipts_qs = receipts_qs.filter(
            Q(reference__icontains=query) |
            Q(payment__student__username__icontains=query) |
            Q(payment__student__first_name__icontains=query) |
            Q(payment__student__last_name__icontains=query) |
            Q(payment__student__email__icontains=query) |
            Q(payment__payment_ref__icontains=query)
        )

    total_issued_amount = receipts_qs.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

    context = {
        'receipts': receipts_qs,
        'query': query,
        'receipts_count': receipts_qs.count(),
        'total_issued_amount': total_issued_amount,
    }
    return render(request, 'payments/accountant_receipts.html', context)


# ==============================================================================
# 6. EXISTING PAYMENT APPROVALS & REVENUE VIEWS (Updated with Accountant Role)
# ==============================================================================

@login_required
@role_required(['hod', 'accountant'])
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
@role_required(['hod', 'accountant'])
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
@role_required(['hod', 'accountant'])
def bulk_apply_discount(request):
    """Applies discounts or agreed custom pricing to a cohort or multiple selected students in 1 click."""
    if request.method == 'POST':
        mode = request.POST.get('mode', 'students')
        discount_type = request.POST.get('discount_type', 'discount_amount')
        amount_raw = request.POST.get('amount', '0').strip()
        reason = request.POST.get('reason', '').strip()

        try:
            val = Decimal(amount_raw)
            if val < 0:
                raise ValueError("Amount cannot be negative.")
        except Exception:
            messages.error(request, "Please enter a valid numeric amount.")
            return redirect(request.META.get('HTTP_REFERER') or 'manage_payments')

        if mode == 'cohort':
            batch_id = request.POST.get('batch_id')
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
@role_required(['hod', 'accountant'])
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

    # Permission check: student owner, accountant, hod, or superuser
    user_role = getattr(getattr(request.user, 'profile', None), 'role', '')
    if not (request.user.is_superuser or request.user == payment.student or user_role in ['accountant', 'hod']):
        messages.error(request, "You do not have permission to view this receipt.")
        return redirect('login')

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
@role_required(['hod', 'accountant'])
def export_monthly_trend_csv(request):
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
@role_required(['hod', 'accountant'])
def revenue_dashboard(request):
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

    course_data = []
    for course in Course.objects.all():
        total_paid = payments.filter(course=course).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        total_due_c = payments.filter(course=course).aggregate(Sum('amount_due'))['amount_due__sum'] or 0
        course_data.append({
            'course': course.name,
            'paid': float(total_paid),
            'due': float(total_due_c),
        })

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
@role_required(['hod', 'accountant'])
def export_revenue_csv(request):
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
    receipts = (
        Receipt.objects
        .filter(payment__student=request.user)
        .select_related('payment', 'payment__course', 'payment__batch')
        .order_by('-issued_date')
    )
    return render(request, 'payments/receipt_center.html', {'receipts': receipts})
