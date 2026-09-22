from django.urls import path
from . import views
from . import views_onboarding

urlpatterns = [
    path('', views.home, name='home'),

    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_user, name='logout_user'),
    path('change-password/', views.change_password_view, name='change_password'),

    # Email verification
    path('verify/<uuid:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    path('verify-email-sent/', views.verify_email_sent, name='verify_email_sent'),


    # Dashboards
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('instructor/dashboard/', views.instructor_dashboard, name='instructor_dashboard'),
    path('hod/dashboard/', views.hod_dashboard, name='hod_dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # Admin Management Command Center Endpoints
    path('admin/students/create/', views.admin_student_create, name='admin_student_create'),
    path('admin/students/<int:profile_id>/batch/', views.admin_student_update_batch, name='admin_student_update_batch'),
    path('admin/students/<int:profile_id>/toggle-status/', views.admin_student_toggle_status, name='admin_student_toggle_status'),
    path('admin/courses/create/', views.admin_course_create, name='admin_course_create'),
    path('admin/courses/<int:course_id>/toggle/', views.admin_course_toggle_publish, name='admin_course_toggle_publish'),
    path('admin/batches/create/', views.admin_batch_create, name='admin_batch_create'),
    path('admin/batches/<int:batch_id>/toggle/', views.admin_batch_toggle_publish, name='admin_batch_toggle_publish'),
    path('admin/payments/record/', views.admin_payment_record, name='admin_payment_record'),
    path('admin/attendance/mark/', views.admin_attendance_mark, name='admin_attendance_mark'),
    path('admin/staff/create/', views.create_staff, name='create_staff'),
    path('admin/staff/approve/<int:user_id>/', views.approve_staff, name='approve_staff'),
    path('admin/staff/<int:user_id>/toggle/', views.admin_staff_toggle_status, name='admin_staff_toggle_status'),
    path('admin/staff/<int:user_id>/delete/', views.admin_staff_delete, name='admin_staff_delete'),

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
