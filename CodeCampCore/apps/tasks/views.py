from django.shortcuts import render, redirect, get_object_or_404
from .models import Task
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def task_list(request):
    tasks = Task.objects.all().order_by('-created_at')
    return render(request, 'tasks/task_list.html', {'tasks': tasks})


@login_required
def create_task(request):
    users = User.objects.all()

    if request.method == 'POST':
        Task.objects.create(
            title=request.POST['title'],
            description=request.POST.get('description'),
            assigned_to_id=request.POST['assigned_to'],
            created_by=request.user,
            priority=request.POST['priority'],
            due_date=request.POST.get('due_date') or None
        )
        return redirect('task_list')

    return render(request, 'tasks/create_task.html', {'users': users})


@login_required
def update_status(request, task_id, status):
    task = get_object_or_404(Task, id=task_id)
    task.status = status
    task.save()
    return redirect('task_list')