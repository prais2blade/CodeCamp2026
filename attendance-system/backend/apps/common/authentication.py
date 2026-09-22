from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class IntegrationAuthentication(BaseAuthentication):

    def authenticate(self, request):

        auth = request.headers.get("Authorization")

        if not auth:
            raise AuthenticationFailed("Missing Authorization header.")

        try:
            keyword, token = auth.split()

        except ValueError:
            raise AuthenticationFailed("Invalid Authorization header.")

        if keyword != "Bearer":
            raise AuthenticationFailed("Invalid authentication type.")

        if token != settings.INTEGRATION_API_KEY:
            raise AuthenticationFailed("Invalid integration key.")

        return (None, None)