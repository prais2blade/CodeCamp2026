from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from apps.students.models import Parent
from apps.students.serializers import ParentLoginSerializer


class ParentLoginAPIView(APIView):

    permission_classes = []

    def post(self, request):

        serializer = ParentLoginSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone_number"]
        password = serializer.validated_data["password"]

        try:
            parent = Parent.objects.get(
                phone_number=phone
            )

        except Parent.DoesNotExist:
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not parent.check_password(password):
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken()

        refresh["parent_id"] = parent.id
        refresh["phone"] = parent.phone_number

        return Response({
            "parent": {
                "id": parent.id,
                "full_name": parent.full_name,
                "phone_number": parent.phone_number,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        })