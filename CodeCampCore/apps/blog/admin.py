from django.contrib import admin
from .models import Post, Category, Tag

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "published", "created_at")
    list_filter = ("published", "category", "tags")
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}

admin.site.register(Category)
admin.site.register(Tag)
