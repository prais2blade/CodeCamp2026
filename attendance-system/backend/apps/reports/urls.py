from django.urls import path
from .views import dashboard_stats
from .api_views import export_attendance_excel, export_students_excel, export_attendance_csv
from .api_views import (
    report_summary_api,
    student_stats_api,
    attendance_trend_api
)

urlpatterns = [

    path(
        "dashboard/stats/",
        dashboard_stats,
        name="dashboard_stats"
    ),
    
    path(
        "summary/",
        report_summary_api
    ),

    path(
        "student-stats/",
        student_stats_api
    ),
    path(
    "trend/",
    attendance_trend_api
),
    path(
    "export/excel/",
    export_attendance_excel
),
    path(
    "export/students/",
    export_students_excel
),
    path(
    "export/csv/",
    export_attendance_csv
),

]