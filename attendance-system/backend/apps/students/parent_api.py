from rest_framework.views import APIView

from .authentication import ParentJWTAuthentication
from .permissions import IsParent


class ParentAPIView(APIView):
    """
    Base class for all Parent Portal APIs.
    """

    authentication_classes = [ParentJWTAuthentication]
    permission_classes = [IsParent]