from django import forms

from .models import Student


class StudentImportForm(forms.Form):
    excel_file = forms.FileField(
        label="Excel File",
        help_text=(
            "Upload the student import template "
            "(.xlsx)"
        ),
    )

    def clean_excel_file(self):
        excel_file = self.cleaned_data[
            "excel_file"
        ]

        if not excel_file.name.endswith(
            ".xlsx"
        ):
            raise forms.ValidationError(
                "Only .xlsx files are supported."
            )

        return excel_file


class StudentForm(forms.ModelForm):

    parent_title = forms.ChoiceField(

        required=False,

        choices=[

            ("", "---------"),

            ("Mr", "Mr"),

            ("Mrs", "Mrs"),

            ("Miss", "Miss"),

            ("Dr", "Dr"),

            ("Pastor", "Pastor"),

            ("Chief", "Chief"),

            ("Alhaji", "Alhaji"),

        ]

    )

    parent_name = forms.CharField(
        required=False,
        label="Parent Name"
    )

    parent_email = forms.EmailField(
        required=False,
        label="Parent Email"
    )

    parent_phone = forms.CharField(
        required=False,
        label="Parent Phone Number"
    )

    parent_whatsapp = forms.CharField(
        required=False,
        label="Parent WhatsApp Number"
    )

    relationship = forms.CharField(
        required=False,
        initial="Guardian",
        label="Relationship"
    )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields[
            "date_of_birth"
        ].input_formats = [
            "%Y-%m-%d"
        ]

        if not self.instance.pk:
            return

        relationship = (
            self.instance.parents
            .select_related("parent")
            .first()
        )

        if not relationship:
            return

        parent = relationship.parent

        self.fields[
            "parent_title"
        ].initial = parent.title

        self.fields[
            "parent_name"
        ].initial = parent.full_name

        self.fields[
            "parent_email"
        ].initial = parent.email

        self.fields[
            "parent_phone"
        ].initial = parent.phone_number

        self.fields[
            "parent_whatsapp"
        ].initial = parent.whatsapp_number

        self.fields[
            "relationship"
        ].initial = relationship.relationship


    def clean(self):
        cleaned_data = super().clean()

        parent_name = (
            cleaned_data.get("parent_name") or ""
        ).strip()

        parent_phone = (
            cleaned_data.get("parent_phone") or ""
        ).strip()

        parent_email = (
            cleaned_data.get("parent_email") or ""
        ).strip()

        relationship = (
            cleaned_data.get("relationship") or ""
        ).strip()

        if parent_name and not parent_phone:
            self.add_error(
                "parent_phone",
                (
                    "Parent phone number is required "
                    "when a parent name is provided."
                ),
            )

        if parent_phone and not parent_name:
            self.add_error(
                "parent_name",
                (
                    "Parent name is required "
                    "when a parent phone number is provided."
                ),
            )

        if parent_email:

            existing_student = (
                Student.objects.filter(
                    parent_name=parent_name,
                )
                .exclude(
                    pk=self.instance.pk,
                )
                .exists()
            )

            if (
                not existing_student
                and not relationship
            ):
                self.add_error(
                    "relationship",
                    (
                        "Relationship is required "
                        "when parent information is provided."
                    ),
                )

        return cleaned_data

    def save(self, commit=True):
        student = super().save(commit=False)

        if student.teaching_class:
            student.class_name = student.teaching_class.name

        if commit:
            student.save()
            self.save_m2m()

        return student

    class Meta:

        model = Student

        fields = [

            "first_name",
            "last_name",
            "photo",
            "date_of_birth",
            "gender",
            "class_name",
            "teaching_class",

        ]

        widgets = {

            "date_of_birth": forms.DateInput(

                attrs={
                    "type": "date"
                },

                format="%Y-%m-%d"

            )

        }
