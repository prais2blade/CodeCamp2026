from django.shortcuts import render, get_object_or_404, redirect
from apps.courses.models import Course

def home(request):
    # Fetch all published Innovation Hub programmes with curriculum and cohorts
    courses = Course.objects.filter(is_published=True).prefetch_related('subjects', 'batches').order_by('name')
    return render(request, "website/home.html", {
        "courses": courses,
        "featured": courses,
        "total_courses": courses.count(),
    })

def about(request):
    return render(request, "website/about.html")

def training_programs(request):
    courses = Course.objects.filter(is_published=True).prefetch_related('subjects', 'batches').order_by('name')
    return render(request, "website/training_programs.html", {"courses": courses})

def course_detail(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    batches = course.batches.filter(is_published=True).order_by('mode', 'session_period')
    subjects = course.subjects.all()
    return render(request, "website/course_detail.html", {
        "course": course,
        "batches": batches,
        "subjects": subjects,
    })

def estate_software(request):
    return render(request, "website/estate.html")

def other_solutions(request):
    return render(request, "website/other_solutions.html")

def contact(request):
    return render(request, "website/contact.html")
