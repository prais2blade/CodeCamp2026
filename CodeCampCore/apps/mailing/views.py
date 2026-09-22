from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import MailingListForm

def join_mailing_list(request):
    form = MailingListForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "You've joined the CodeCamp Core mailing list!")
        return redirect(request.META.get('HTTP_REFERER', '/'))
    return render(request, 'mailing/join.html', {'form': form})
