
from django.utils import timezone
from rest_framework.response import Response
from apps.students.parent_api import ParentAPIView
from apps.students.models import StudentParent
from apps.attendance.models import Attendance


class ParentDashboardAPIView(ParentAPIView):

    def get(self, request):

        parent = request.user
        today = timezone.localdate()

        children = []

        present_today = 0
        absent_today = 0

        relationships = (
            StudentParent.objects
            .select_related("student")
            .filter(parent=parent)
        )

        for relation in relationships:

            student = relation.student

            attendance = (
                Attendance.objects
                .filter(
                    student=student,
                    date=today
                )
                .first()
            )

            if attendance:

                present_today += 1

                attendance_data = {
                    "status": attendance.status,
                    "check_in": attendance.check_in,
                    "check_out": attendance.check_out,
                }

            else:

                absent_today += 1

                attendance_data = {
                    "status": "Absent",
                    "check_in": None,
                    "check_out": None,
                }

            children.append({

                "id": student.id,

                "student_id": student.student_id,

                "full_name": student.full_name,

                "class_name": student.class_name,

                "relationship": relation.relationship,

                "attendance_today": attendance_data

            })

        return Response({

            "parent": {

                "id": parent.id,

                "full_name": parent.full_name,

                "phone_number": parent.phone_number,

                "email": parent.email,

            },

            "summary": {

                "children": len(children),

                "present_today": present_today,

                "absent_today": absent_today,

            },

            "children": children

        })
        