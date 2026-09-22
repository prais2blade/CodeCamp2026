from django import forms
from django.contrib.auth.forms import PasswordChangeForm

from .models import Announcement, Assignment, TeachingClass


class StaffLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "class": (
                    "w-full rounded-lg border border-slate-300 px-4 py-3 "
                    "outline-none focus:border-blue-600 focus:ring-2 "
                    "focus:ring-blue-100"
                ),
            }
        ),
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "class": (
                    "w-full rounded-lg border border-slate-300 px-4 py-3 "
                    "outline-none focus:border-blue-600 focus:ring-2 "
                    "focus:ring-blue-100"
                ),
            }
        ),
    )


class StaffPasswordChangeForm(PasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                (
                    "w-full rounded-lg border border-slate-300 px-4 py-3 "
                    "outline-none focus:border-blue-600 focus:ring-2 "
                    "focus:ring-blue-100"
                ),
            )


class StaffAssignmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["teaching_class"].queryset = get_staff_classes(user)

        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                (
                    "w-full rounded-lg border border-slate-300 px-4 py-3 "
                    "outline-none focus:border-blue-600 focus:ring-2 "
                    "focus:ring-blue-100"
                ),
            )

    class Meta:
        model = Assignment
        fields = [
            "title",
            "description",
            "teaching_class",
            "due_date",
            "attachment",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 5,
                }
            ),
            "due_date": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),
        }


class StaffAnnouncementForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["teaching_class"].queryset = get_staff_classes(user)

        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                (
                    "w-full rounded-lg border border-slate-300 px-4 py-3 "
                    "outline-none focus:border-blue-600 focus:ring-2 "
                    "focus:ring-blue-100"
                ),
            )

    class Meta:
        model = Announcement
        fields = [
            "title",
            "message",
            "teaching_class",
            "attachment",
            "expires_at",
            "is_active",
        ]
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "rows": 5,
                }
            ),
            "expires_at": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                }
            ),
        }


def get_staff_classes(user):
    queryset = TeachingClass.objects.filter(is_active=True)

    if user.is_superuser or getattr(user, "role", "") == "ADMIN":
        return queryset.order_by("name")

    return queryset.filter(staff=user).order_by("name")
