from django.db import transaction

from apps.students.models import (
    Parent,
    Student,
    StudentParent,
)


class RegistrationIntegrationService:

    """
    Creates or reuses a Parent,
    creates a Student,
    links both together.
    """

    @classmethod
    @transaction.atomic
    def register(cls, data):

        parent = cls.get_or_create_parent(data)

        student = cls.create_student(data)

        StudentParent.objects.get_or_create(

            parent=parent,

            student=student,

            defaults={
                "relationship": data["relationship"]
            }

        )

        return {

            "success": True,

            "student_id": student.student_id,

            "parent_id": parent.id,

        }

    @classmethod
    def get_or_create_parent(cls, data):

        parent = Parent.objects.filter(

            phone_number=data["parent_phone"]

        ).first()

        if parent:

            return parent

        parent = Parent(

            full_name=data["parent_name"],

            phone_number=data["parent_phone"],

            whatsapp_number=data.get(
                "parent_whatsapp",
                "",
            ),

            email=data["parent_email"],

        )

        # Temporary password
        parent.set_password("CodeCamp2026")

        parent.save()

        return parent

    @classmethod
    def create_student(cls, data):

        student = Student.objects.create(

            first_name=data["first_name"],

            last_name=data["last_name"],

            class_name=data["batch"],

        )

        return student