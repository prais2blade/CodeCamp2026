from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.authentication import CoreAPIKeyAuthentication
from apps.courses.models import Course, Subject
from apps.scheduling.models import Batch, ClassSession


class CourseCatalogAPIView(APIView):
    """
    Exposes the master Academy course catalog.
    """

    authentication_classes = [CoreAPIKeyAuthentication]
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        courses = Course.objects.filter(is_published=True).order_by("name")
        data = []
        for course in courses:
            subjects = [
                {"id": s.id, "name": s.name, "description": s.description}
                for s in course.subjects.all()
            ]
            data.append({
                "id": course.id,
                "name": course.name,
                "slug": course.slug,
                "short_description": course.short_description,
                "duration_weeks": course.duration_weeks,
                "fee": str(course.fee),
                "subjects": subjects,
            })
        return Response({"courses": data, "count": len(data)}, status=status.HTTP_200_OK)


class BatchCatalogAPIView(APIView):
    """
    Exposes active Academy batches with scheduling and capacity status.
    """

    authentication_classes = [CoreAPIKeyAuthentication]
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        course_id = request.query_params.get("course_id")
        batches_qs = Batch.objects.filter(is_published=True).select_related("course")
        if course_id:
            batches_qs = batches_qs.filter(course_id=course_id)

        data = []
        for batch in batches_qs:
            sessions = [
                {
                    "day": session.day,
                    "time_period": session.time_period,
                    "subject": session.subject.name,
                }
                for session in batch.sessions.select_related("subject").all()
            ]
            data.append({
                "id": batch.id,
                "name": batch.name,
                "course_id": batch.course.id,
                "course_name": batch.course.name,
                "course_slug": batch.course.slug,
                "mode": batch.mode,
                "batch_type": batch.batch_type,
                "session_period": batch.session_period,
                "days_pattern": batch.days_pattern,
                "start_date": batch.start_date.isoformat(),
                "end_date": batch.end_date.isoformat(),
                "max_students": batch.max_students,
                "current_students": batch.current_students,
                "is_full": batch.is_full,
                "sessions": sessions,
            })
        return Response({"batches": data, "count": len(data)}, status=status.HTTP_200_OK)
