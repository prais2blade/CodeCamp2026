from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import ProfileCompletionForm
from .utils import get_dashboard_url_name


@login_required
def welcome(request):
    profile = request.user.profile

    # 🔒 Block wrong access
    if profile.onboarding_stage == 'email_pending':
        return redirect('login')

    if profile.onboarding_stage not in ['welcome', 'onboarding_steps', 'complete_profile', 'finished']:
        return redirect('welcome')

    # Progress forward only if at correct stage
    if profile.onboarding_stage == 'welcome':
        profile.onboarding_stage = 'onboarding_steps'
        profile.save()

    return render(request, 'accounts/welcome.html')


@login_required
def onboarding_steps(request):
    profile = request.user.profile

    # 🔒 Prevent skipping
    if profile.onboarding_stage == 'welcome':
        return redirect('welcome')

    if profile.onboarding_stage not in ['onboarding_steps', 'complete_profile', 'finished']:
        return redirect('welcome')

    if profile.onboarding_stage == 'onboarding_steps':
        profile.onboarding_stage = 'complete_profile'
        profile.save()

    return render(request, 'accounts/onboarding_steps.html')


@login_required
def complete_profile(request):
    profile = request.user.profile

    # 🔒 Prevent skipping
    if profile.onboarding_stage in ['welcome', 'onboarding_steps']:
        return redirect('welcome')

    if request.method == 'POST':
        form = ProfileCompletionForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            profile.onboarding_stage = 'finished'
            profile.save()
            return redirect(get_dashboard_url_name(profile))
    else:
        form = ProfileCompletionForm(instance=profile)

    return render(request, 'accounts/complete_profile.html', {'form': form})

@login_required
def onboarding_complete(request):
    return render(request, 'accounts/onboarding_complete.html')
