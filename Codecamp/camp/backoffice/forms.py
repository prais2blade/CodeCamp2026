from django import forms
from django.contrib.auth.forms import AuthenticationForm


class CustomLoginForm(AuthenticationForm):
    """
    Staff Login Form
    """

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "placeholder": "Username",
                "autocomplete": "username",
            }
        )
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        )
    )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        css = (
            "block w-full rounded-lg border border-gray-300 "
            "px-3 py-2 shadow-sm "
            "focus:border-purple-500 "
            "focus:ring-purple-500 "
            "sm:text-sm"
        )

        for field in self.fields.values():

            existing = field.widget.attrs.get(
                "class",
                ""
            )

            field.widget.attrs["class"] = (
                f"{existing} {css}"
            ).strip()
            
            
from django import forms

from teencamp.models import Batch


class BatchForm(forms.ModelForm):

    class Meta:
        model = Batch

        fields = [
            "name",
            "priority",
            "capacity",
            "reporting_time",
            "start_date",
            "end_date",
            "reserved_for_existing_students",
            "accept_new_registrations",
            "is_active",
        ]

        widgets = {

            "name": forms.TextInput(attrs={
                "class":"w-full border rounded-lg px-4 py-3"
            }),

            "priority": forms.NumberInput(attrs={
                "class":"w-full border rounded-lg px-4 py-3"
            }),

            "capacity": forms.NumberInput(attrs={
                "class":"w-full border rounded-lg px-4 py-3"
            }),

            "reporting_time": forms.TimeInput(
                attrs={
                    "type":"time",
                    "class":"w-full border rounded-lg px-4 py-3"
                }
            ),

            "start_date": forms.DateInput(
                attrs={
                    "type":"date",
                    "class":"w-full border rounded-lg px-4 py-3"
                }
            ),

            "end_date": forms.DateInput(
                attrs={
                    "type":"date",
                    "class":"w-full border rounded-lg px-4 py-3"
                }
            ),
        }