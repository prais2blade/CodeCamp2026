from django.shortcuts import render, get_object_or_404, redirect
from apps.courses.models import Course

def home(request):
    # show some featured published courses
    featured = Course.objects.filter(is_published=True)[:6]
    return render(request, "website/home.html", {"featured": featured})

def about(request):
    return render(request, "website/about.html")

def training_programs(request):
    courses = Course.objects.filter(is_published=True).order_by('-created_at')
    return render(request, "website/training_programs.html", {"courses": courses})

def course_detail(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug, is_published=True)
    return render(request, "website/course_detail.html", {"course": course})

def estate_software(request):
    return render(request, "website/estate.html")

def other_solutions(request):
    return render(request, "website/other_solutions.html")

def contact(request):
    return render(request, "website/contact.html")
