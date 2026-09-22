from django import forms
from .models import Course, Subject
from django.contrib.auth.models import User

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "name",
            "short_description",
            "description",
            "duration_weeks",
            "fee",
            "image",
            "brochure",
            "is_published",
        ]

        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Apply AdminLTE-friendly styling
        for field in self.fields.values():
            field.widget.attrs.update({
                "class": "form-control"
            })
            
            


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'description', 'instructor']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter only instructors
        self.fields['instructor'].queryset = User.objects.filter(profile__role='instructor')

        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})