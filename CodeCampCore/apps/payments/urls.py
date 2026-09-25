from django.urls import path
from . import views

urlpatterns = [
    # Student Views
    path('my-payments/', views.student_payments, name='student_payments'),
    path('receipts/', views.receipt_center, name='receipt_center'),
    path('receipt/<int:receipt_id>/', views.view_receipt, name='view_receipt'),

    # Accountant & HOD Financial Views
    path('accountant/dashboard/', views.accountant_dashboard, name='accountant_dashboard'),
    path('debtors-ledger/', views.debtors_ledger, name='debtors_ledger'),
    path('record-payment/', views.record_payment, name='record_payment'),
    path('accountant/receipts/', views.accountant_receipts, name='accountant_receipts'),
    path('export-reconciliation-excel/', views.export_reconciliation_excel, name='export_reconciliation_excel'),

    # Payment Approvals & Management
    path('manage/', views.manage_payments, name='manage_payments'),
    path('approvals/', views.manage_payments, name='payment_approvals'),
    path('approve/<int:payment_id>/', views.approve_payment, name='approve_payment'),
    path('bulk-discount/', views.bulk_apply_discount, name='bulk_apply_discount'),
    path('update/<int:payment_id>/', views.update_payment_status, name='update_payment'),
    path('revenue-dashboard/', views.revenue_dashboard, name='revenue_dashboard'),
    path('export-csv/', views.export_revenue_csv, name='export_revenue_csv'),
    path('export-trend-csv/', views.export_monthly_trend_csv, name='export_monthly_trend_csv'),
]
