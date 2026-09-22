from rest_framework.permissions import BasePermission

from .models import Parent


class IsParent(BasePermission):
    """
    Allows access only to authenticated Parent users.
    """

    def has_permission(self, request, view):
        return (
            request.user is not None
            and isinstance(request.user, Parent)
        )