from rest_framework.response import Response
from rest_framework.views import APIView


class ParentProfileAPIView(APIView):

    def get(self, request):

        parent = request.user

        return Response({
            "id": parent.id,
            "full_name": parent.full_name,
            "phone_number": parent.phone_number,
            "email": parent.email,
        })