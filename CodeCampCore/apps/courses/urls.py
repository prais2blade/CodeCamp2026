from django.urls import path
from . import views

urlpatterns = [
    # Student
    path('choose/', views.choose_course, name='choose_course'),
    path('my-course/', views.student_course, name='student_course'),

    # Admin / HOD
    path('manage/', views.manage_courses, name='manage_courses'),
    path('create/', views.course_create, name='course_create'),
    path('edit/<int:pk>/', views.course_edit, name='course_edit'),

    # Existing toggle
    path('toggle/<int:course_id>/', views.toggle_course_status, name='toggle_course_status'),
    
    # SUBJECT MANAGEMENT
    path('subjects/<int:course_id>/', views.manage_subjects, name='manage_subjects'),
    path('subjects/create/<int:course_id>/', views.create_subject, name='create_subject'),
    path('subjects/edit/<int:pk>/', views.edit_subject, name='edit_subject'),

    # INSTRUCTOR VIEW
    path('my-subjects/', views.instructor_subjects, name='instructor_subjects'),
    # ATTENDANCE
    path('attendance/<int:subject_id>/', views.mark_attendance, name='mark_attendance'),
    
    # ASSIGNMENTS & RUBRIC GRADING
    path('instructor/assignments/', views.instructor_assignments, name='instructor_assignments'),
    path('assignments/create/', views.create_assignment, name='create_assignment_general'),
    path('assignments/create/<int:subject_id>/', views.create_assignment, name='create_assignment'),
    path('assignments/<int:subject_id>/', views.manage_assignments, name='manage_assignments'),
    path('assignments/<int:assignment_id>/submissions/', views.assignment_submissions, name='assignment_submissions'),
    path('submissions/<int:submission_id>/grade/', views.grade_submission, name='grade_submission'),
    path('student/assignments/submit/<int:assignment_id>/', views.submit_assignment, name='submit_assignment'),
    path('student/gradebook/', views.student_weekly_gradebook, name='student_weekly_gradebook'),
    path('student/assignments/', views.student_assignments, name='student_assignments'),
]
