from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile
from .services.attendance_sync_service import AttendanceSyncService


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
    elif hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=Profile)
def sync_student_profile(sender, instance, **kwargs):
    if instance.batch:
        instance.batch.check_capacity()

    # Automatically synchronize student profile with Attendance System
    if instance.role == 'student':
        # Avoid recursion when only external_attendance_id was updated
        update_fields = kwargs.get('update_fields')
        if update_fields and set(update_fields) == {'external_attendance_id'}:
            return
        try:
            if not instance.external_attendance_id or not instance.external_attendance_id.startswith('CDCP-'):
                AttendanceSyncService.sync_or_register_student(instance)
            else:
                AttendanceSyncService.sync_student_details_to_attendance(instance)
        except Exception:
            pass
