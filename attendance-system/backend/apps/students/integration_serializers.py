from rest_framework import serializers


class RegisterStudentSerializer(serializers.Serializer):

    first_name = serializers.CharField()

    last_name = serializers.CharField()

    parent_name = serializers.CharField()

    parent_phone = serializers.CharField()

    parent_whatsapp = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    parent_email = serializers.EmailField()

    relationship = serializers.CharField()

    batch = serializers.CharField()

    mode = serializers.CharField()