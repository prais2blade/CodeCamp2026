from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from apps.accounts.models import Profile


class RegisterAPI(APIView):

    def post(self, request):

        username = request.data.get("username")
        email = request.data.get("email")
        password = request.data.get("password")

        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Username already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        Profile.objects.create(user=user)

        return Response(
            {"message": "Account created successfully"},
            status=status.HTTP_201_CREATED
        )
        
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token


class LoginAPI(APIView):

    def post(self, request):

        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(username=username, password=password)

        if not user:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            "token": token.key,
            "username": user.username
        })

from rest_framework.permissions import IsAuthenticated


class StudentDashboardAPI(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user
        profile = user.profile

        data = {
            "username": user.username,
            "email": user.email,
            "course": profile.course.name if profile.course else None,
        }

        return Response(data)

class TeacherDashboardAPI(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        user = request.user
        profile = user.profile

        data = {
            "username": user.username,
            "email": user.email,
            "department": profile.department.name if profile.department else None,
        }

        return Response(data)