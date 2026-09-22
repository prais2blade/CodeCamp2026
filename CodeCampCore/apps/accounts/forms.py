from django import forms
from .models import Profile

class ProfileCompletionForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone', 'avatar']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control-file'}),
        }
