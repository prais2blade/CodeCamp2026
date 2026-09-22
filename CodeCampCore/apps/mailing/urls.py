from django.urls import path
from . import views

urlpatterns = [
    path('join/', views.join_mailing_list, name='join_mailing_list'),
]
