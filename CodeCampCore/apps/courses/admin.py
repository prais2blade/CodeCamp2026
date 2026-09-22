from django.contrib import admin
from .models import Course, Subject

class SubjectInline(admin.TabularInline):
    model = Subject
    extra = 1

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    inlines = [SubjectInline]

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'instructor')
