from django.urls import re_path
from .consumer import DashboardConsumer

websocket_urlpatterns = [
    re_path(r"ws/backoffice/$", DashboardConsumer.as_asgi()),
]
