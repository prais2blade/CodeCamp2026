from rest_framework import serializers

from .models import Attendance

class AttendanceHistorySerializer(
    serializers.ModelSerializer
):

    date = serializers.DateField()

    check_in = serializers.SerializerMethodField()

    check_out = serializers.SerializerMethodField()

    class Meta:

        model = Attendance

        fields = [

            "date",

            "check_in",

            "check_out"

        ]

    def get_check_in(self, obj):

        if obj.check_in:

            return obj.check_in.strftime(
                "%I:%M %p"
            )

        return "-"

    def get_check_out(self, obj):

        if obj.check_out:

            return obj.check_out.strftime(
                "%I:%M %p"
            )

        return "-"


class AttendanceTodaySerializer(
    serializers.ModelSerializer
):

    student_id = serializers.CharField(
        source="student.student_id"
    )

    name = serializers.SerializerMethodField()

    class_name = serializers.CharField(
        source="student.class_name"
    )

    check_in = serializers.SerializerMethodField()

    status = serializers.SerializerMethodField()

    class Meta:

        model = Attendance

        fields = [

            "student_id",

            "name",

            "class_name",

            "check_in",

            "status",

        ]

    def get_name(self, obj):

        return (
            f"{obj.student.first_name} "
            f"{obj.student.last_name}"
        )

    def get_check_in(self, obj):

        if obj.check_in:

            return obj.check_in.strftime(
                "%I:%M %p"
            )

        return "-"

    def get_status(self, obj):

        if obj.check_out:

            return "CHECKED OUT"

        if obj.check_in:

            return "IN CENTER"

        return "ABSENT"