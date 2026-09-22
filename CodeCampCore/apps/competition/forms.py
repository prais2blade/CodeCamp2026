from django import forms
from django.contrib.auth import get_user_model
from .models import CompetitionParticipant, CompetitionTeam, CompetitionScore, CompetitionEdition

User = get_user_model()


class CompetitionRegistrationForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput, label='Confirm password')

    full_name = forms.CharField(max_length=200)
    phone = forms.CharField(max_length=30, required=False)
    track = forms.ChoiceField(choices=CompetitionParticipant.TRACK_CHOICES)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already used.")
        return email

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get('password')
        cpwd = cleaned.get('confirm_password')
        if pwd and cpwd and pwd != cpwd:
            self.add_error('confirm_password', "Passwords do not match.")
        return cleaned


class CompetitionLoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class TeamCreateForm(forms.ModelForm):
    class Meta:
        model = CompetitionTeam
        fields = ('name', 'track')


class TeamJoinForm(forms.Form):
    join_code = forms.CharField(max_length=12, label="Team join code")


class JudgeScoreForm(forms.ModelForm):
    class Meta:
        model = CompetitionScore
        fields = ('round', 'raw_score', 'comment')
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3}),
        }


class EditionSelectForm(forms.Form):
    edition = forms.ModelChoiceField(
        queryset=CompetitionEdition.objects.all().order_by('-year'),
        required=True,
        label="Edition"
    )
