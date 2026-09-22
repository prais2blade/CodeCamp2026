from rest_framework.response import Response
from rest_framework import status
from apps.students.parent_api import ParentAPIView
from apps.students.models import StudentParent
from apps.attendance.models import Attendance

class ParentStudentHistoryAPIView(ParentAPIView):

    def get(self, request, student_id):

        parent = request.user

        relation = (
            StudentParent.objects
            .select_related("student")
            .filter(
                parent=parent,
                student_id=student_id
            )
            .first()
        )

        if relation is None:

            return Response(
                {
                    "detail": "Access denied."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        student = relation.student

        attendance_records = (
            Attendance.objects
            .filter(student=student)
            .order_by("-date")
        )

        history = []

        for record in attendance_records:

            history.append({

                "date": record.date,

                "status": record.status,

                "check_in": record.check_in,

                "check_out": record.check_out,

            })

        return Response({

            "student": {

                "id": student.id,

                "student_id": student.student_id,

                "full_name": student.full_name,

                "class_name": student.class_name,

                "relationship": relation.relationship,

            },

            "history": history

        })