import os


settings_env = os.getenv("DJANGO_ENV", "development").lower()

if settings_env in {"production", "prod"}:
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
