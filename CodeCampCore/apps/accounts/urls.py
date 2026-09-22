from django.urls import path
from . import views
from . import views_onboarding

urlpatterns = [
    path('', views.home, name='home'),

    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_user, name='logout_user'),

    # Email verification
    path('verify/<uuid:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    path('verify-email-sent/', views.verify_email_sent, name='verify_email_sent'),


    # Dashboards
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('instructor/dashboard/', views.instructor_dashboard, name='instructor_dashboard'),
    path('hod/dashboard/', views.hod_dashboard, name='hod_dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # Profile
    path('student/profile/', views.student_profile, name='student_profile'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),

    # Attendance & Messages
    path('student/attendance/', views.student_view_attendance, name='student_view_attendance'),
    path('messages/', views.student_messages, name='student_messages'),

    # Onboarding
    path('welcome/', views_onboarding.welcome, name='welcome'),
    path('onboarding/', views_onboarding.onboarding_steps, name='onboarding_steps'),
    path('complete-profile/', views_onboarding.complete_profile, name='complete_profile'),
    path('onboarding-complete/', views_onboarding.onboarding_complete, name='onboarding_complete'),
]
