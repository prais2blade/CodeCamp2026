from django import forms
from .models import MailingList

class MailingListForm(forms.ModelForm):
    class Meta:
        model = MailingList
        fields = ['email']
