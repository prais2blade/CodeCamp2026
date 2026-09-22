from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Batch, ClassSession
from apps.accounts.decorators import role_required
from apps.payments.models import Payment
from apps.accounts.decorators import payment_required

@login_required
@role_required('hod')
def batch_detail(request, batch_id):
    batch = Batch.objects.get(id=batch_id)
    sessions = batch.sessions.all().order_by('day')
    return render(request, 'scheduling/batch_detail.html', {'batch': batch, 'sessions': sessions})


@login_required
@role_required('student')
@payment_required
def student_timetable(request):
    batch = request.user.profile.batch
    if not batch:
        messages.warning(request, "You are not assigned to any batch yet.")
        return redirect('student_dashboard')
    sessions = batch.sessions.all().order_by('day')
    return render(request, 'scheduling/student_timetable.html', {'batch': batch, 'sessions': sessions})


@login_required
@role_required('student')
def choose_batch(request):
    profile = request.user.profile
    if not profile.course:
        messages.warning(request, "Please choose a course first.")
        return redirect('choose_course')

    batches = Batch.objects.filter(
        course=profile.course,
        is_published=True
    ).order_by('start_date')

    if request.method == 'POST':
        batch_id = request.POST.get('batch_id')
        if batch_id:
            batch = Batch.objects.get(id=batch_id)
            batch.check_capacity()

            if batch.is_full:
                messages.info(request, "This batch is full. A new session will open soon.")
                return redirect('choose_batch')

            # Assign batch
            profile.batch = batch
            profile.save()

            # ---------------------------------------
            # AUTO-CREATE PAYMENT (your original code)
            # ---------------------------------------
            if not Payment.objects.filter(
                student=request.user,
                course=profile.course,
                batch=batch
            ).exists():

                payment = Payment.objects.create(
                    student=request.user,
                    course=profile.course,
                    batch=batch,
                    amount_due=profile.course.fee,
                )
                payment.calculate_monthly_payment()
            # ---------------------------------------

            batch.check_capacity()
            messages.success(request, f"You have successfully joined {batch.name}.")
            return redirect('student_timetable')

    return render(request, 'scheduling/choose_batch.html', {'batches': batches})


@login_required
@role_required('hod')
def manage_batches(request):
    batches = Batch.objects.select_related('course').order_by('-start_date')
    return render(request, 'scheduling/manage_batches.html', {'batches': batches})

@login_required
@role_required('hod')
def toggle_batch_status(request, batch_id):
    batch = Batch.objects.get(id=batch_id)
    batch.is_published = not batch.is_published
    batch.save()
    state = "published" if batch.is_published else "deactivated"
    messages.success(request, f"Batch '{batch.name}' {state}.")
    return redirect('manage_batches')
