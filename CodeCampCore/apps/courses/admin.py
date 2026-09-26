from django.contrib import admin
from .models import Course, Subject, Assignment, Submission

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

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'batch', 'week_number', 'due_date', 'max_score', 'created_at')
    list_filter = ('subject__course', 'batch', 'week_number', 'due_date')
    search_fields = ('title', 'subject__name', 'description')

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'status', 'total_score', 'letter_grade', 'submitted_at')
    list_filter = ('status', 'letter_grade', 'assignment__subject__course')
    search_fields = ('student__username', 'student__email', 'assignment__title')

