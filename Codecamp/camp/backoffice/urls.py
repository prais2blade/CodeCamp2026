from django.contrib.auth.views import LogoutView
from django.urls import path

from .forms import CustomLoginForm
from .views import (
    BatchDetail,
    Dashboard,
    RegistrationDetail,
    RegistrationList,
    StaffLoginView,
    dashboard_json,
    export_csv,
    toggle_payment,
    sync_pending_registrations,
    BatchList,
    BatchUpdate,
)

app_name = "backoffice"

urlpatterns = [

    # =====================================================
    # Dashboard
    # =====================================================

    path(
        "",
        Dashboard.as_view(),
        name="dashboard",
    ),

    path(
        "dashboard/data/",
        dashboard_json,
        name="dashboard-json",
    ),

    # =====================================================
    # Registrations
    # =====================================================

    path(
        "registrations/",
        RegistrationList.as_view(),
        name="registrations",
    ),

    path(
        "registrations/<int:pk>/",
        RegistrationDetail.as_view(),
        name="reg-detail",
    ),

    path(
        "registrations/<int:pk>/approve/",
        toggle_payment,
        name="reg-approve",
    ),

    path(
        "export/registrations.csv",
        export_csv,
        name="export-csv",
    ),

    # =====================================================
    # Authentication
    # =====================================================

    path(
        "accounts/login/",
        StaffLoginView.as_view(),
        name="login",
    ),

    path(
        "accounts/logout/",
        LogoutView.as_view(
            next_page="backoffice:login"
        ),
        name="logout",
    ),
    
    path(
        "sync/",
        sync_pending_registrations,
        name="sync-pending",
    ),
    
    path(
        "batches/",
        BatchList.as_view(),
        name="batches",
    ),
    
    path(
        "batches/<int:pk>/",
        BatchDetail.as_view(),
        name="batch-detail",
    ),

path(
    "batches/<int:pk>/edit/",
    BatchUpdate.as_view(),
    name="batch-update",
),
    
]