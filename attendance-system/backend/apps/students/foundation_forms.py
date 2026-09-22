from django import forms


FIELD_CLASS = (
    "w-full rounded-lg border border-slate-300 px-4 py-3 "
    "text-slate-900 outline-none focus:border-emerald-700 "
    "focus:ring-2 focus:ring-emerald-100"
)


class FoundationLoginForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "class": FIELD_CLASS,
                "placeholder": "foundation@example.com",
            }
        ),
    )

    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "class": FIELD_CLASS,
                "placeholder": "Enter your password",
            }
        ),
    )


class FoundationPasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        label="Current password",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "class": FIELD_CLASS,
            }
        ),
    )

    new_password = forms.CharField(
        label="New password",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "class": FIELD_CLASS,
            }
        ),
    )

    confirm_password = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "class": FIELD_CLASS,
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password and new_password != confirm_password:
            self.add_error(
                "confirm_password",
                "Passwords do not match.",
            )

        return cleaned_data
