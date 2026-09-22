from django.utils import timezone

from rest_framework.response import Response
from rest_framework.decorators import api_view

from .models import Attendance
from .serializers import (
    AttendanceTodaySerializer
)
from apps.students.models import Student

from .serializers import (
    AttendanceHistorySerializer
)


@api_view(["GET"])
def attendance_today(request):

    today = timezone.localdate()

    queryset = Attendance.objects.filter(
        date=today
    ).select_related(
        "student"
    )

    serializer = (
        AttendanceTodaySerializer(
            queryset,
            many=True
        )
    )

    return Response(
        serializer.data
    )
    
    
@api_view(["GET"])
def attendance_history(

    request,

    student_id

):

    student = Student.objects.get(

        student_id=student_id

    )

    records = (

        Attendance.objects

        .filter(

            student=student

        )

        .order_by(

            "-date"

        )[:10]

    )

    serializer = (

        AttendanceHistorySerializer(

            records,

            many=True

        )

    )

    return Response(

        serializer.data

    )