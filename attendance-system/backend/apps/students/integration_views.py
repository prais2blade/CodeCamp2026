from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import IntegrationAuthentication
from .serializers import RegisterStudentSerializer
from .services import RegistrationIntegrationService

class RegisterStudentAPIView(APIView):

    authentication_classes = [
        IntegrationAuthentication
    ]

    permission_classes = []

    def post(self, request):

        serializer = RegisterStudentSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        payload = dict(serializer.validated_data)
        payload["_base_url"] = request.build_absolute_uri("/")
        result = RegistrationIntegrationService.register(payload)

        return Response({

            "success": True,

            "student_id": result["student"].student_id,

            "parent_id": result["parent"].id,

            "parent_created": result["parent_created"],

            "student_created": result["student_created"],

            "temporary_password": result["temporary_password"],
        })
