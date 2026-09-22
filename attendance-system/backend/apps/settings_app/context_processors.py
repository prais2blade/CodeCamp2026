from django.conf import settings

from .models import SystemSettings


def system_settings(request):

    settings_obj = (
        SystemSettings.objects.first()
    )

    return {

        "system_settings":
            settings_obj,

        "codecamp_back_office_url":
            settings.CODECAMP_BACK_OFFICE_URL

    }
