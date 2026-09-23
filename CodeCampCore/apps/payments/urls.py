from django.urls import path
from . import views

urlpatterns = [
    path('my-payments/', views.student_payments, name='student_payments'),
    path('manage/', views.manage_payments, name='manage_payments'),
    path('approvals/', views.manage_payments, name='payment_approvals'),
    path('approve/<int:payment_id>/', views.approve_payment, name='approve_payment'),
    path('bulk-discount/', views.bulk_apply_discount, name='bulk_apply_discount'),
    path('update/<int:payment_id>/', views.update_payment_status, name='update_payment'),
    path('receipt/<int:receipt_id>/', views.view_receipt, name='view_receipt'),
    path('revenue-dashboard/', views.revenue_dashboard, name='revenue_dashboard'),
    path('export-csv/', views.export_revenue_csv, name='export_revenue_csv'),
    path('export-trend-csv/', views.export_monthly_trend_csv, name='export_monthly_trend_csv'),
    path('receipts/', views.receipt_center, name='receipt_center'),
]
