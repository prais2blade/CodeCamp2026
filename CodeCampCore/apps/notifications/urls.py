from django.urls import path
from . import views

urlpatterns = [
    path('', views.notification_center, name='notification_center'),
    path('detail/<int:pk>/', views.notification_detail, name='notification_detail'),
    path('resend/<int:pk>/', views.resend_notification, name='resend_notification'),
    path('export-csv/', views.export_notifications_csv, name='export_notifications_csv'),
    path('analytics/', views.notification_analytics, name='notification_analytics'),
    path('resend-failed/', views.resend_failed_notifications, name='resend_failed_notifications'),
]
