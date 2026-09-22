from django.urls import path
from .views import CampLanding, CampRegister, CampSuccess, VirtualRegistrationView, sync_pending_registrations


app_name = "teencamp"

urlpatterns = [
    path("",               CampLanding.as_view(),  name="landing"),
    path("register/",      CampRegister.as_view(), name="register"),
    path("register/done/", CampSuccess.as_view(),  name="success"),
    path(
        "register/done/<str:reg_code>/",
        CampSuccess.as_view(),
        name="success",
    ),
    path(
        "sync-pending/",
        sync_pending_registrations,
        name="sync-pending",
    ),
]
