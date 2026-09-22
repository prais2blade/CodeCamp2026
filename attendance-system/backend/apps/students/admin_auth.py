from functools import wraps

from django.shortcuts import redirect
from django.urls import reverse


def is_admin_portal_user(user):
    return user.is_authenticated and (
        user.is_superuser
        or getattr(user, "role", "") == "ADMIN"
    )


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if is_admin_portal_user(request.user):
            return view_func(request, *args, **kwargs)

        login_url = reverse("school_admin:login")
        return redirect(f"{login_url}?next={request.path}")

    return wrapped
