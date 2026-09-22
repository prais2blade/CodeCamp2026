from django.db import models

from apps.students.models import Student


class Attendance(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE
    )
    

    date = models.DateField()

    check_in = models.DateTimeField(
        null=True,
        blank=True
    )

    check_out = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = (
            "student",
            "date"
        )

    @property
    def status(self):
        if self.check_out:
            return "CHECKED OUT"

        if self.check_in:
            return "IN CENTER"

        return "ABSENT"

    def __str__(self):
        return f"{self.student.student_id} - {self.date}"
