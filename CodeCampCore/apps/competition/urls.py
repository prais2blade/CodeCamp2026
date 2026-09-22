from django.urls import path
from . import views

app_name = 'competition'

urlpatterns = [
    # Root -> redirect to active edition
    path('', views.root_redirect, name='root'),

    # Archive of all editions
    path('archive/', views.archive, name='archive'),

    # Edition-prefixed URLs
    path('<int:year>/', views.home, name='home'),
    path('<int:year>/about/', views.about, name='about'),
    path('<int:year>/categories/', views.categories, name='categories'),
    path('<int:year>/judges/', views.judges, name='judges'),
    path('<int:year>/gallery/', views.gallery, name='gallery'),
    path('<int:year>/sponsors/', views.sponsors, name='sponsors'),
    path('<int:year>/contact/', views.contact, name='contact'),
    path('<int:year>/schedule/', views.schedule, name='schedule'),
    path('<int:year>/rules/', views.rules, name='rules'),
    path('<int:year>/prizes/', views.prizes, name='prizes'),

    # Auth / participant
    path('<int:year>/register/', views.register, name='register'),
    path('<int:year>/login/', views.login_view, name='login'),
    path('<int:year>/logout/', views.logout_view, name='logout'),
    path('<int:year>/dashboard/', views.dashboard, name='dashboard'),
    path('<int:year>/qr/<int:participant_id>/', views.qr_code_image, name='qr'),
    path('<int:year>/ticket/', views.ticket_pdf, name='ticket_pdf'),

    # Team management
    path('<int:year>/team/create/', views.team_create, name='team_create'),
    path('<int:year>/team/join/', views.team_join, name='team_join'),

    # Staff check-in
    path('<int:year>/staff/checkin/', views.staff_checkin, name='staff_checkin'),
    path('<int:year>/staff/checkin/search/', views.search_participant, name='staff_search'),
    path('<int:year>/staff/checkin/do/<int:pk>/', views.do_checkin, name='staff_do_checkin'),

    # Leaderboard + judges
    path('<int:year>/leaderboard/', views.leaderboard, name='leaderboard'),
    path('<int:year>/judge/', views.judge_dashboard, name='judge_dashboard'),
    path('<int:year>/judge/score/<int:participant_id>/', views.judge_score, name='judge_score'),
]
