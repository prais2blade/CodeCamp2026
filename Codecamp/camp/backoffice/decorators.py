from functools import wraps

from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
)
from django.core.exceptions import PermissionDenied


def is_staff_user(user):
    """
    Returns True if the authenticated user is a staff member.
    """

    return (
        user.is_authenticated
        and user.is_staff
    )


def staff_required(view_func):
    """
    Decorator for function-based views.
    """

    @wraps(view_func)
    @login_required
    @user_passes_test(is_staff_user)
    def wrapper(request, *args, **kwargs):
        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapper


def staff_required_class(view):
    """
    Decorator for class-based views.
    """

    return login_required(
        user_passes_test(
            is_staff_user
        )(view)
    )


def superuser_required(view_func):
    """
    Restrict access to superusers only.
    """

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):

        if not request.user.is_superuser:
            raise PermissionDenied(
                "Superuser access required."
            )

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapper