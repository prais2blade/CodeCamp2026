from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import ParentJWTAuthentication
from .serializers import (
    ParentChangePasswordSerializer,
    ParentLoginSerializer,
    ParentProfileSerializer,
    RegisterStudentSerializer,
)
from .services import (
    ParentChildService,
    ParentDashboardService,
    ParentLoginService,
    ParentPasswordService,
    ParentProfileService,
    RegistrationIntegrationService,
    TimelineService,
)


class RegisterStudentAPIView(APIView):
    """
    Register a student through the API.
    """

    permission_classes = [
        AllowAny,
    ]

    authentication_classes = []

    def post(self, request):
        serializer = RegisterStudentSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            payload = dict(serializer.validated_data)
            payload["_base_url"] = request.build_absolute_uri("/")
            result = RegistrationIntegrationService.register(payload)
        except ValueError as exc:
            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {
                    "success": False,
                    "message": "Unable to complete registration.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "success": True,
                "student": {
                    "id": result["student"].id,
                    "student_id": result["student"].student_id,
                    "created": result["student_created"],
                },
                "parent": {
                    "id": result["parent"].id,
                    "created": result["parent_created"],
                },
                "temporary_password": result["temporary_password"],
            },
            status=status.HTTP_201_CREATED,
        )


class ParentLoginAPIView(APIView):
    """
    Authenticate a parent and issue JWT tokens.
    """

    permission_classes = [
        AllowAny,
    ]

    authentication_classes = []

    def post(self, request):
        serializer = ParentLoginSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            result = ParentLoginService.login(
                phone_number=serializer.validated_data["phone_number"],
                password=serializer.validated_data["password"],
            )
        except ValueError as exc:
            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,
                "access": result["access"],
                "refresh": result["refresh"],
                "must_change_password": result["must_change_password"],
                "parent": {
                    "id": result["parent"].id,
                    "title": result["parent"].title,
                    "full_name": result["parent"].full_name,
                    "phone_number": result["parent"].phone_number,
                    "email": result["parent"].email,
                },
            },
            status=status.HTTP_200_OK,
        )


class ParentChangePasswordAPIView(APIView):
    """
    Allow an authenticated parent to change their password.
    """

    authentication_classes = [
        ParentJWTAuthentication,
    ]

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request):
        serializer = ParentChangePasswordSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        try:
            ParentPasswordService.change_password(
                parent=request.user,
                current_password=serializer.validated_data["current_password"],
                new_password=serializer.validated_data["new_password"],
                confirm_password=serializer.validated_data["confirm_password"],
            )
        except ValueError as exc:
            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,
                "message": "Password changed successfully.",
            },
            status=status.HTTP_200_OK,
        )


class ParentDashboardAPIView(APIView):
    """
    Return the authenticated parent's dashboard.
    """

    authentication_classes = [
        ParentJWTAuthentication,
    ]

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        dashboard = ParentDashboardService.get_dashboard(request.user)

        return Response(
            {
                "success": True,
                "data": dashboard,
            },
            status=status.HTTP_200_OK,
        )


class ParentProfileAPIView(APIView):
    """
    Retrieve and update the authenticated parent's profile.
    """

    authentication_classes = [
        ParentJWTAuthentication,
    ]

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        profile = ParentProfileService.get_profile(request.user)

        return Response(
            {
                "success": True,
                "data": profile,
            },
            status=status.HTTP_200_OK,
        )

    def put(self, request):
        serializer = ParentProfileSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        parent = ParentProfileService.update_profile(
            parent=request.user,
            data=serializer.validated_data,
        )

        profile = ParentProfileService.get_profile(parent)

        return Response(
            {
                "success": True,
                "message": "Profile updated successfully.",
                "data": profile,
            },
            status=status.HTTP_200_OK,
        )


class ParentChildAPIView(APIView):
    authentication_classes = [
        ParentJWTAuthentication,
    ]

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        student_id,
    ):
        try:
            result = ParentChildService.get_child(
                request.user,
                student_id,
            )
        except ValueError as exc:
            return Response(
                {
                    "success": False,
                    "message": str(exc),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "data": result,
            }
        )


class ParentTimelineAPIView(APIView):
    """
    Return the authenticated parent's timeline.
    """

    authentication_classes = [
        ParentJWTAuthentication,
    ]

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        timeline = TimelineService.get_timeline(request.user)

        return Response(
            {
                "success": True,
                "count": len(timeline),
                "results": timeline,
            },
            status=status.HTTP_200_OK,
        )
