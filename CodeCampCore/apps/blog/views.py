from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Post, Category, Tag
from django.core.paginator import Paginator




def blog_list(request):
    posts = Post.objects.filter(published=True).order_by("-created_at")
    categories = Category.objects.all()
    posts_qs = Post.objects.filter(published=True).order_by("-created_at")
    paginator = Paginator(posts_qs, 6)
    page = request.GET.get("page")
    posts = paginator.get_page(page)
    return render(request, "blog/blog_list.html", {
        "posts": posts,
        "categories": categories,
        "meta_title": "Tech Guides & Updates | CodeCamp Blog",
        "meta_description": "Learn about coding, software, data, cloud, AI and more from CodeCamp."        
    })    
    

def blog_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, published=True)
    related = Post.objects.filter(category=post.category).exclude(id=post.id)[:3]

    return render(request, "blog/blog_detail.html", {
        "post": post,
        "related": related,
        "meta_title": post.meta_title,
        "meta_description": post.meta_description,
    })

def blog_category(request, slug):
    category = get_object_or_404(Category, slug=slug)
    posts = Post.objects.filter(category=category, published=True)
    return render(request, "blog/blog_category.html", {"posts": posts, "category": category})

def blog_tag(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    posts = Post.objects.filter(tags=tag, published=True)
    return render(request, "blog/blog_tag.html", {"posts": posts, "tag": tag})

def blog_search(request):
    q = request.GET.get("q", "")
    posts = Post.objects.filter(
        Q(title__icontains=q) |
        Q(excerpt__icontains=q) |
        Q(body__icontains=q)
    ).filter(published=True)
    return render(request, "blog/blog_search.html", {"posts": posts, "query": q})
