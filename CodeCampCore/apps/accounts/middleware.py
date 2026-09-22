from django.shortcuts import redirect
from django.urls import reverse
from apps.accounts.utils import get_next_onboarding_url

ONBOARDING_ALLOWED_PATHS = [
    'login',
    'logout_user',
    'register',
    'verify_email',
    'verify_email_sent',
    'resend_verification',
]


class OnboardingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip admin and static
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        resolver = request.resolver_match
        if resolver and 'competition' in resolver.namespaces:
            return self.get_response(request)

        profile = getattr(request.user, 'profile', None)
        if not profile:
            return self.get_response(request)

        next_url_name = get_next_onboarding_url(profile)
        if not next_url_name:
            return self.get_response(request)
        if not resolver or not resolver.url_name:
            return self.get_response(request)

        if (
            resolver.url_name not in ONBOARDING_ALLOWED_PATHS
            and resolver.url_name != next_url_name
        ):
            return redirect(reverse(next_url_name))

        return self.get_response(request)
