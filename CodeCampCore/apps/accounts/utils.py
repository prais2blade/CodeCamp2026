ROLE_DASHBOARD_URLS = {
    "student": "student_dashboard",
    "instructor": "instructor_dashboard",
    "hod": "hod_dashboard",
    "accountant": "accountant_dashboard",
}


def get_next_onboarding_url(profile):
    if not profile.is_verified:
        return None

    stage = profile.onboarding_stage

    if stage == "welcome":
        return "welcome"

    elif stage == "onboarding_steps":
        return "onboarding_steps"

    elif stage == "complete_profile":
        return "complete_profile"

    elif stage == "finished":
        return None

    # 🔥 SAFETY FALLBACK
    return "welcome"

def get_dashboard_url_name(profile):
    role = getattr(profile, "role", "student")
    return ROLE_DASHBOARD_URLS.get(role, "student_dashboard")
