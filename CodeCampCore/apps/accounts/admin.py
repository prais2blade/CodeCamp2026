import datetime
from decimal import Decimal
from django.contrib import admin, messages
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.utils import timezone

from .models import Attendance, Profile
from apps.payments.models import Payment
from apps.scheduling.models import Batch


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'role',
        'course',
        'batch',
        'start_date',
        'external_attendance_id',
        'is_verified',
        'is_approved',
        'has_paid',
    )
    list_filter = ('role', 'is_verified', 'is_approved', 'has_paid', 'start_date', 'course', 'batch')
    search_fields = (
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'phone',
        'external_attendance_id',
    )
    actions = ['bulk_update_start_date']

    @admin.action(description="📅 Update Start Date & Recalculate Payment Billing")
    def bulk_update_start_date(self, request, queryset):
        if 'apply' in request.POST:
            start_date_str = request.POST.get('start_date')
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
            except Exception:
                self.message_user(request, "Invalid start date provided.", level=messages.ERROR)
                return HttpResponseRedirect(request.get_full_path())

            update_due_date = request.POST.get('update_due_date') == 'on'
            align_batch = request.POST.get('align_batch') == 'on'

            updated_count = 0
            for profile in queryset:
                profile.start_date = start_date

                # Optional: Align batch for the course
                if align_batch and profile.course:
                    matching_batch = Batch.objects.filter(
                        course=profile.course,
                        start_date=start_date
                    ).first()
                    if not matching_batch:
                        matching_batch = Batch.objects.filter(
                            course=profile.course,
                            is_published=True
                        ).order_by('start_date').first()
                    if matching_batch:
                        profile.batch = matching_batch

                profile.save()

                # Update or initialize Payment record accordingly
                payment = Payment.objects.filter(student=profile.user, course=profile.course).first()
                if not payment:
                    payment = Payment.objects.filter(student=profile.user).first()
                if not payment:
                    amount_due = profile.course.fee if (profile.course and profile.course.fee and profile.course.fee > 0) else Decimal('35000.00')
                    payment = Payment.objects.create(
                        student=profile.user,
                        course=profile.course,
                        batch=profile.batch,
                        amount_due=amount_due,
                        amount_paid=profile.paid_amount or Decimal('0.00'),
                        monthly_payment=Decimal('35000.00'),
                        status='paid' if profile.has_paid else 'pending'
                    )

                payment.billing_start_date = start_date
                if update_due_date:
                    payment.next_due_date = start_date + datetime.timedelta(days=30)
                if profile.batch:
                    payment.batch = profile.batch
                payment.save()

                updated_count += 1

            self.message_user(
                request,
                f"Successfully updated start date to {start_date} and recalculated billing schedule for {updated_count} student(s).",
                level=messages.SUCCESS
            )
            return HttpResponseRedirect(request.get_full_path())

        context = {
            'opts': self.model._meta,
            'profiles': queryset,
            'today_iso': timezone.localdate().isoformat(),
        }
        return render(request, 'admin/accounts/profile/bulk_update_start_date.html', context)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'subject',
        'batch',
        'date',
        'status',
        'source',
        'external_reference',
        'marked_by',
    )
    list_filter = ('status', 'source', 'date', 'subject', 'batch')
    search_fields = (
        'student__username',
        'student__email',
        'subject__name',
        'batch__name',
        'external_reference',
    )
    date_hierarchy = 'date'
