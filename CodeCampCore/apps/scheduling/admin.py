from django.contrib import admin
from .models import Batch, ClassSession

class ClassSessionInline(admin.TabularInline):
    model = ClassSession
    extra = 1

class BatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'mode', 'batch_type', 'session_period',
                    'start_date', 'end_date', 'max_students', 'is_published')
    list_filter = ('course', 'mode', 'batch_type', 'is_published')

admin.site.register(Batch, BatchAdmin)

@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('batch', 'subject', 'day', 'time_period', 'duration_hours')
