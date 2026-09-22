from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class IntegrationAuthentication(BaseAuthentication):

    """
    Simple Bearer Token authentication
    for trusted internal systems.
    """

    keyword = "Bearer"

    def authenticate(self, request):

        auth = request.headers.get("Authorization")

        if not auth:
            raise AuthenticationFailed(
                "Authorization header missing."
            )

        try:

            keyword, token = auth.split()

        except ValueError:

            raise AuthenticationFailed(
                "Invalid Authorization header."
            )

        if keyword != self.keyword:

            raise AuthenticationFailed(
                "Invalid authentication type."
            )

        if token != settings.INTEGRATION_API_KEY:

            raise AuthenticationFailed(
                "Invalid integration key."
            )

        return (None, None)