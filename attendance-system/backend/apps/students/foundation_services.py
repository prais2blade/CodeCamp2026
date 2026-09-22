from datetime import timedelta

from django.utils import timezone

from apps.attendance.models import Attendance

from .models import PerformanceRecord, StudentFoundation


def normalize_monitoring_days(value, default=30):
    try:
        days = int(value)
    except (TypeError, ValueError):
        return default

    if days not in {30, 60, 90, 180, 365}:
        return default

    return days


def get_student_attendance_summary(student, days=30):
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    records = Attendance.objects.filter(
        student=student,
        date__range=[
            start_date,
            today,
        ],
    )
    present_days = records.values("date").distinct().count()
    checked_out_days = records.filter(
        check_out__isnull=False,
    ).values("date").distinct().count()
    latest = records.order_by(
        "-date",
        "-check_in",
    ).first()
    attendance_rate = 0

    if days:
        attendance_rate = round((present_days / days) * 100, 1)

    return {
        "start_date": start_date,
        "end_date": today,
        "days": days,
        "present_days": present_days,
        "checked_out_days": checked_out_days,
        "attendance_rate": attendance_rate,
        "latest": latest,
    }


def get_foundation_student_rows(foundation, days=30):
    links = (
        StudentFoundation.objects.filter(
            foundation=foundation,
            is_active=True,
            student__is_active=True,
        )
        .select_related(
            "student",
            "student__teaching_class",
        )
        .order_by(
            "student__first_name",
            "student__last_name",
        )
    )
    rows = []

    for link in links:
        performance_records = PerformanceRecord.objects.filter(
            student=link.student,
            visible_to_foundations=True,
        )
        rows.append(
            {
                "link": link,
                "student": link.student,
                "attendance": get_student_attendance_summary(
                    link.student,
                    days=days,
                ),
                "latest_performance": performance_records.first(),
                "performance_count": performance_records.count(),
            }
        )

    return rows
