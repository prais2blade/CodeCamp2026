from django.apps import AppConfig


class TeencampConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'teencamp'

    def ready(self):
        from . import signals
