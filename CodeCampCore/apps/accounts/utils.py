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


def generate_qr_code_data_uri(url):
    """Generates a PNG base64 Data URI for embedding in HTML & PDF templates."""
    try:
        import qrcode
        from io import BytesIO
        import base64
        qr = qrcode.QRCode(
            version=1,
            box_size=4,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None

