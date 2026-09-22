from django.contrib import admin
from .models import Payment, Receipt


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'course',
        'batch',
        'amount_due',
        'amount_paid',
        'monthly_payment',
        'status',
        'billing_start_date',
        'next_due_date',
        'payment_date',
    )
    list_filter = ('status', 'course', 'batch', 'billing_start_date', 'next_due_date')
    search_fields = (
        'student__username',
        'student__email',
        'student__first_name',
        'student__last_name',
        'course__name',
        'payment_ref',
    )
    date_hierarchy = 'payment_date'


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = (
        'payment',
        'amount',
        'reference',
        'issued_date',
    )
    list_filter = ('issued_date',)
    search_fields = (
        'payment__student__username',
        'payment__student__email',
        'reference',
    )
    date_hierarchy = 'issued_date'
