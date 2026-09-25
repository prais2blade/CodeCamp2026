import datetime
from decimal import Decimal
from django.contrib import admin, messages
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.utils import timezone

from .models import Attendance, Profile, SummerCertificate
from apps.payments.models import Payment
from apps.scheduling.models import Batch


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'role',
        'student_status',
        'course',
        'batch',
        'start_date',
        'external_attendance_id',
        'is_verified',
        'is_approved',
        'has_paid',
    )
    list_filter = (
        'student_status',
        ('course', admin.RelatedOnlyFieldListFilter),
        ('batch', admin.RelatedOnlyFieldListFilter),
        'has_paid',
        'start_date',
        'role',
        'is_verified',
        'is_approved',
    )
    search_fields = (
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'phone',
        'external_attendance_id',
        'course__name',
        'batch__name',
    )
    actions = ['bulk_update_start_date', 'deactivate_summer_students', 'activate_continuing_students']

    @admin.action(description="🏖️ Transition to Summer Alumni (Deactivate for Next Term)")
    def deactivate_summer_students(self, request, queryset):
        count = 0
        for profile in queryset.filter(role='student'):
            profile.student_status = 'summer_alumni'
            profile.has_paid = False  # Tuition required for next term
            profile.save(update_fields=['student_status', 'has_paid'])
            count += 1
        self.message_user(
            request,
            f"Successfully transitioned {count} student(s) to Summer Alumni (Inactive). They can view reports and download certificates, but must register and pay to reactivate for the main term.",
            level=messages.SUCCESS
        )

    @admin.action(description="✅ Reactivate Selected Students for Active Term")
    def activate_continuing_students(self, request, queryset):
        count = 0
        for profile in queryset.filter(role='student'):
            profile.student_status = 'active'
            profile.has_paid = True
            profile.save(update_fields=['student_status', 'has_paid'])
            count += 1
        self.message_user(
            request,
            f"Successfully reactivated {count} student(s) to Active Status.",
            level=messages.SUCCESS
        )

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
            reassign_course_id = request.POST.get('reassign_course')
            reassign_course = None

            if reassign_course_id:
                from apps.courses.models import Course
                try:
                    reassign_course = Course.objects.get(id=reassign_course_id)
                except Course.DoesNotExist:
                    pass

            updated_profiles_count = 0
            updated_payments_count = 0
            matched_batch_count = 0

            for profile in queryset:
                profile.start_date = start_date
                update_fields = ['start_date']

                if reassign_course:
                    profile.course = reassign_course
                    update_fields.append('course')

                target_course = reassign_course if reassign_course else profile.course

                if align_batch and target_course:
                    matching_batch = Batch.objects.filter(
                        course=target_course,
                        start_date=start_date
                    ).first()
                    if matching_batch:
                        profile.batch = matching_batch
                        update_fields.append('batch')
                        matched_batch_count += 1

                profile.save(update_fields=update_fields)
                updated_profiles_count += 1

                payments = Payment.objects.filter(student=profile.user)
                for payment in payments:
                    payment.billing_start_date = start_date
                    p_update_fields = ['billing_start_date']

                    if reassign_course:
                        payment.course = reassign_course
                        if hasattr(reassign_course, 'fee') and reassign_course.fee:
                            payment.amount_due = reassign_course.fee
                        p_update_fields.extend(['course', 'amount_due'])

                    if align_batch and profile.batch:
                        payment.batch = profile.batch
                        p_update_fields.append('batch')

                    if update_due_date:
                        payment.next_due_date = start_date
                        p_update_fields.append('next_due_date')

                    payment.update_status()
                    payment.calculate_monthly_payment()
                    payment.save(update_fields=p_update_fields)
                    updated_payments_count += 1

            msg = (
                f"Successfully updated start date to {start_date} for {updated_profiles_count} student profile(s) "
                f"and synchronized {updated_payments_count} payment record(s)!"
            )
            if reassign_course:
                msg += f" Reassigned program to '{reassign_course.name}'."
            if align_batch:
                msg += f" Linked {matched_batch_count} student(s) to matching cohorts."

            self.message_user(request, msg, level=messages.SUCCESS)
            return HttpResponseRedirect(request.get_full_path())

        from apps.courses.models import Course
        context = {
            'opts': self.model._meta,
            'profiles': queryset,
            'today_iso': timezone.localdate().isoformat(),
            'courses': Course.objects.all(),
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


@admin.register(SummerCertificate)
class SummerCertificateAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'title',
        'course',
        'grade_or_score',
        'issue_date',
        'reference_id',
        'has_file',
        'uploaded_by',
    )
    list_filter = ('course', 'issue_date', 'grade_or_score')
    search_fields = (
        'student__username',
        'student__email',
        'student__first_name',
        'student__last_name',
        'reference_id',
        'title',
    )

    def has_file(self, obj):
        return bool(obj.certificate_file)
    has_file.boolean = True
