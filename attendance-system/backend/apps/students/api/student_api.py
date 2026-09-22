from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from apps.students.models import Parent
from apps.students.serializers import ParentLoginSerializer
from apps.students.models import Student, StudentParent
from apps.students.serializers import (
    StudentDetailSerializer
)
from apps.students.serializers import (
    StudentListSerializer
)


def get_parent_from_token(request):
    jwt_auth = JWTAuthentication()
    header = jwt_auth.get_header(request)
    if header is None:
        return None

    try:
        raw_token = jwt_auth.get_raw_token(header)
        validated_token = jwt_auth.get_validated_token(raw_token)
    except Exception:
        return None

    parent_id = validated_token.get("parent_id")
    if not parent_id:
        return None

    try:
        return Parent.objects.get(id=parent_id)
    except Parent.DoesNotExist:
        return None


@api_view(["GET"])
def student_detail_api(
    request,
    student_id
):

    student = get_object_or_404(

        Student,

        student_id=student_id

    )

    serializer = (

        StudentDetailSerializer(

            student,

            context={
                "request": request
            }

        )

    )

    return Response(
        serializer.data
    )
    
@api_view(["GET"])
def student_list_api(request):

    students = Student.objects.all()

    serializer = (

        StudentListSerializer(

            students,

            many=True,

            context={
                "request": request
            }

        )

    )

    return Response(
        serializer.data
    )