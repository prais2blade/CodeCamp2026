from django.urls import path
from . import views

app_name = 'assessments'

urlpatterns = [
    # Web views
    path('', views.student_assessment_hub, name='student_hub'),
    path('problem/<slug:slug>/', views.problem_workspace, name='problem_workspace'),
    path('tutor/queue/', views.tutor_defense_queue, name='tutor_queue'),

    # REST APIs
    path('api/problems/', views.PracticalProblemListAPIView.as_view(), name='api_problems_list'),
    path('api/problems/<slug:slug>/', views.PracticalProblemDetailAPIView.as_view(), name='api_problem_detail'),
    path('api/run/', views.RunCodeAPIView.as_view(), name='api_run_code'),
    path('api/defense/<int:session_id>/', views.DefenseSessionAPIView.as_view(), name='api_defense_session'),
    path('api/defense/answer/', views.SubmitDefenseAnswerAPIView.as_view(), name='api_defense_answer'),
    path('api/tutor/review/', views.TutorDefenseReviewAPIView.as_view(), name='api_tutor_review'),
    path('api/tutor/review/<int:session_id>/', views.TutorDefenseReviewAPIView.as_view(), name='api_tutor_review_detail'),
]
