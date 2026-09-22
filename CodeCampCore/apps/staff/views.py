from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.accounts.decorators import role_required

@login_required
@role_required('hod')
def manage_instructors(request):
    from apps.accounts.models import Profile
    instructors = Profile.objects.filter(role='instructor')
    return render(request, 'staff/manage_instructors.html', {'instructors': instructors})
