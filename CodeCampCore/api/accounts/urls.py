from django.urls import path
from .views import RegisterAPI, LoginAPI, StudentDashboardAPI

urlpatterns = [

    path("register/", RegisterAPI.as_view()),
    path("login/", LoginAPI.as_view()),
    path("dashboard/", StudentDashboardAPI.as_view()),

]