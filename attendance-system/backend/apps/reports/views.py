from django.utils import timezone
from django.http import JsonResponse

from apps.students.models import Student
from apps.attendance.models import Attendance


def dashboard_stats(request):

    today = timezone.localdate()

    total_students = Student.objects.count()

    present = Attendance.objects.filter(
        date=today
    ).count()

    checked_out = Attendance.objects.filter(
        date=today,
        check_out__isnull=False
    ).count()

    absent = (
        total_students - present
    )

    return JsonResponse({

        "total_students":
            total_students,

        "present":
            present,

        "checked_out":
            checked_out,

        "absent":
            absent,

    })