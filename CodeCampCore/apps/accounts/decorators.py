from django.shortcuts import redirect
from django.shortcuts import redirect
from django.contrib import messages

def role_required(role):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if request.user.profile.role != role:
                return redirect('login')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def payment_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.has_paid:
            messages.warning(request, "Please complete at least your first monthly payment to access your dashboard.")
            return redirect('student_payments')
        return view_func(request, *args, **kwargs)
    return wrapper
