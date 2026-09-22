from django.conf import settings

from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Parent


# ==========================================================
# Parent JWT Authentication
# ==========================================================

class ParentJWTAuthentication(JWTAuthentication):
    """
    Authenticate Parent using JWT.

    The JWT contains:

        parent_id
        phone
    """

    def authenticate(self, request):

        header = self.get_header(request)

        if header is None:
            return None

        raw_token = self.get_raw_token(header)

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)

        parent_id = validated_token.get("parent_id")

        if not parent_id:
            raise exceptions.AuthenticationFailed(
                "Invalid parent token."
            )

        try:

            parent = Parent.objects.get(
                id=parent_id
            )

        except Parent.DoesNotExist:

            raise exceptions.AuthenticationFailed(
                "Parent account not found."
            )

        return (
            parent,
            validated_token,
        )


# ==========================================================
# Integration Authentication
# ==========================================================

class IntegrationAuthentication(BaseAuthentication):
    """
    Authentication for trusted server-to-server requests
    coming from the CodeCamp platform.
    """

    def authenticate(self, request):
        api_key = self.get_api_key(request)

        if api_key is None:
            raise exceptions.AuthenticationFailed("Missing API Key.")

        if api_key not in self.valid_api_keys():
            raise exceptions.AuthenticationFailed("Invalid API Key.")

        class IntegrationUser:
            is_authenticated = True
            username = "codecamp"

        return (IntegrationUser(), None)

    def get_api_key(self, request):
        api_key = request.headers.get("X-API-KEY")

        if api_key:
            return api_key

        authorization = request.headers.get("Authorization", "")

        try:
            auth_type, token = authorization.split()
        except ValueError:
            return None

        if auth_type.lower() != "bearer":
            return None

        return token

    def valid_api_keys(self):
        ignored_values = {
            "",
            "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET",
        }

        keys = {
            settings.ATTENDANCE_API_KEY,
            getattr(settings, "INTEGRATION_API_KEY", None),
        }

        return {
            key
            for key in keys
            if key and key not in ignored_values
        }


# ==========================================================
# Helper
# ==========================================================

def get_parent_from_token(request):

    token = request.auth

    if not token:
        return None

    parent_id = token.get("parent_id")

    if not parent_id:
        return None

    try:

        return Parent.objects.get(
            id=parent_id
        )

    except Parent.DoesNotExist:

        return None
