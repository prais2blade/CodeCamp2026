from django import forms


class ParentLoginForm(forms.Form):
    phone_number = forms.CharField(
        label="Phone number",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "tel",
                "class": (
                    "w-full rounded-lg border border-slate-300 px-4 py-3 "
                    "text-slate-900 outline-none focus:border-blue-600 "
                    "focus:ring-2 focus:ring-blue-100"
                ),
                "placeholder": "08012345678",
            }
        ),
    )

    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "class": (
                    "w-full rounded-lg border border-slate-300 px-4 py-3 "
                    "text-slate-900 outline-none focus:border-blue-600 "
                    "focus:ring-2 focus:ring-blue-100"
                ),
                "placeholder": "Enter your password",
            }
        ),
    )


class ParentPasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        label="Current password",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "class": (
                    "w-full rounded-lg border border-slate-300 px-4 py-3 "
                    "text-slate-900 outline-none focus:border-blue-600 "
                    "focus:ring-2 focus:ring-blue-100"
                ),
            }
        ),
    )

    new_password = forms.CharField(
        label="New password",
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "class": (
                    "w-full rounded-lg border border-slate-300 px-4 py-3 "
                    "text-slate-900 outline-none focus:border-blue-600 "
                    "focus:ring-2 focus:ring-blue-100"
                ),
            }
        ),
    )

    confirm_password = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "class": (
                    "w-full rounded-lg border border-slate-300 px-4 py-3 "
                    "text-slate-900 outline-none focus:border-blue-600 "
                    "focus:ring-2 focus:ring-blue-100"
                ),
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
