from django.urls import path
from . import views

urlpatterns = [
    path('choose-batch/', views.choose_batch, name='choose_batch'),
    path('timetable/', views.student_timetable, name='student_timetable'),
    path('manage/', views.manage_batches, name='manage_batches'),
    path('toggle/<int:batch_id>/', views.toggle_batch_status, name='toggle_batch_status'),
]
