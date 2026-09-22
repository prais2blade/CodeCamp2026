# camp/urls.py  (project root)

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    # 🔐 1) Custom login/logout FIRST
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="backoffice/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(next_page="login"),
        name="logout",
    ),

    # 🏢 2) Back‑office section
    path("backoffice/", include("backoffice.urls")),

    # 🌐 3) Public site (blank prefix) LAST
    path("", include("teencamp.urls")),

    # ⚙️ 4) Admin
    path("admin/", admin.site.urls),
]
