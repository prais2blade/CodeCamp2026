from django import forms

from teencamp.models import CodingCampRegistration


class CodingCampRegistrationForm(forms.ModelForm):
    """
    Teen CodeCamp Registration Form

    Uses the Praisetent Design System (PDS)
    styling and widgets.
    """

    class Meta:
        model = CodingCampRegistration

        fields = (
            "first_name",
            "last_name",
            "age",
            "mode",
            "parent_name",
            "relationship",
            "parent_phone",
            "parent_whatsapp",
            "parent_email",
            "receipt",
        )

        widgets = {

            "first_name": forms.TextInput(
                attrs={
                    "class": "pds-input",
                    "placeholder": "Student First Name",
                    "autocomplete": "given-name",
                }
            ),

            "last_name": forms.TextInput(
                attrs={
                    "class": "pds-input",
                    "placeholder": "Student Last Name",
                    "autocomplete": "family-name",
                }
            ),

            "age": forms.NumberInput(
                attrs={
                    "class": "pds-input",
                    "placeholder": "Age",
                    "min": 8,
                    "max": 18,
                }
            ),

            "mode": forms.Select(
                attrs={
                    "class": "pds-select",
                }
            ),

            "parent_name": forms.TextInput(
                attrs={
                    "class": "pds-input",
                    "placeholder": "Parent / Guardian Name",
                    "autocomplete": "name",
                }
            ),

            "relationship": forms.Select(
                attrs={
                    "class": "pds-select",
                }
            ),

            "parent_phone": forms.TextInput(
                attrs={
                    "class": "pds-input",
                    "placeholder": "08012345678",
                    "autocomplete": "tel",
                }
            ),

            "parent_whatsapp": forms.TextInput(
                attrs={
                    "class": "pds-input",
                    "placeholder": "08012345678",
                    "autocomplete": "tel",
                }
            ),

            "parent_email": forms.EmailInput(
                attrs={
                    "class": "pds-input",
                    "placeholder": "parent@email.com",
                    "autocomplete": "email",
                }
            ),

            "receipt": forms.ClearableFileInput(
                attrs={
                    "class": "pds-input",
                    "accept": "image/*,.pdf",
                }
            ),
        }

        labels = {
            "first_name": "Student First Name",
            "last_name": "Student Last Name",
            "age": "Student Age",
            "mode": "Learning Mode",
            "parent_name": "Parent / Guardian",
            "relationship": "Relationship",
            "parent_phone": "Phone Number",
            "parent_whatsapp": "WhatsApp Number",
            "parent_email": "Email Address",
            "receipt": "Payment Receipt",
        }

        help_texts = {
            "receipt": "Upload your bank payment receipt (PDF or image).",
            "parent_whatsapp": "Required for camp updates and notifications.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make important fields required
        required_fields = (
            "first_name",
            "last_name",
            "age",
            "mode",
            "parent_name",
            "relationship",
            "parent_phone",
            "parent_email",
            "receipt",
        )

        for field_name in required_fields:
            self.fields[field_name].required = True

        # Optional WhatsApp
        self.fields["parent_whatsapp"].required = False

    # ==========================================================
    # Validation
    # ==========================================================

    def clean_parent_email(self):
        """
        Normalize email address.
        """
        return self.cleaned_data["parent_email"].strip().lower()

    def clean_parent_phone(self):
        """
        Remove spaces from phone number.
        """
        return self.cleaned_data["parent_phone"].replace(" ", "")

    def clean_parent_whatsapp(self):
        """
        Remove spaces from WhatsApp number.
        """
        value = self.cleaned_data.get("parent_whatsapp")

        if value:
            return value.replace(" ", "")

        return value

    def clean_age(self):
        """
        Camp accepts students aged 8–45.
        """
        age = self.cleaned_data["age"]

        if not 8 <= age <= 45:
            raise forms.ValidationError(
                "CodeCamp is available only for students between 8 and 45 years old."
            )

        return age