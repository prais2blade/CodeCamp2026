from django.urls import path
from . import views

app_name = "website"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("training/", views.training_programs, name="training_programs"),
    path("training/<slug:course_slug>/", views.course_detail, name="course_detail"),
    path("estate-software/", views.estate_software, name="estate_software"),
    path("software-solutions/", views.other_solutions, name="software_solutions"),
    path("contact/", views.contact, name="contact"),
]
