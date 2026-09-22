from django.urls import path
from . import views

app_name = "blog"

urlpatterns = [
    path("", views.blog_list, name="list"),
    path("search/", views.blog_search, name="search"),
    path("category/<slug:slug>/", views.blog_category, name="category"),
    path("tag/<slug:slug>/", views.blog_tag, name="tag"),
    path("<slug:slug>/", views.blog_detail, name="detail"),
]
