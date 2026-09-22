from rest_framework import serializers

from .models import (
    Student,
    StudentParent,
    Parent
)
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class StudentDetailSerializer(
    serializers.ModelSerializer
):

    parent = serializers.SerializerMethodField()

    photo = serializers.SerializerMethodField()

    class Meta:

        model = Student

        fields = [

            "student_id",

            "first_name",

            "last_name",

            "class_name",

            "gender",

            "photo",

            "parent",

        ]

    def get_photo(self, obj):

        request = self.context.get(
            "request"
        )

        if obj.photo:

            return request.build_absolute_uri(
                obj.photo.url
            )

        return None

    def get_parent(self, obj):

        link = StudentParent.objects.filter(
            student=obj
        ).select_related(
            "parent"
        ).first()

        if not link:

            return None

        parent = link.parent

        return {

            "name":
                parent.full_name,

            "phone":
                parent.phone_number,

            "email":
                parent.email,

            "whatsapp":
                parent.whatsapp_number,

        }


class StudentListSerializer(
    serializers.ModelSerializer
):

    photo = serializers.SerializerMethodField()

    parent_name = serializers.SerializerMethodField()

    class Meta:

        model = Student

        fields = [

            "student_id",

            "first_name",

            "last_name",

            "class_name",

            "gender",

            "photo",

            "parent_name",

        ]

    def get_photo(self, obj):

        request = self.context.get(
            "request"
        )

        if obj.photo:

            return request.build_absolute_uri(
                obj.photo.url
            )

        return None

    def get_parent_name(self, obj):

        link = StudentParent.objects.filter(
            student=obj
        ).select_related(
            "parent"
        ).first()

        if not link:

            return "N/A"

        return link.parent.full_name
    

class ParentLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField()
    
    

class ParentChildSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    student_id = serializers.CharField()
    full_name = serializers.CharField()
    class_name = serializers.CharField()
    attendance_today = serializers.BooleanField()
    
    
class ParentJWTAuthentication(JWTAuthentication):
    """
    Authenticate Parent using JWT.
    The JWT contains:
        parent_id
        phone
    """

    def authenticate(self, request):
        header = self.get_header(request)

        if header is None:
            return None

        raw_token = self.get_raw_token(header)

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)

        parent_id = validated_token.get("parent_id")

        if not parent_id:
            raise exceptions.AuthenticationFailed(
                "Invalid parent token."
            )

        try:
            parent = Parent.objects.get(id=parent_id)

        except Parent.DoesNotExist:
            raise exceptions.AuthenticationFailed(
                "Parent account not found."
            )

        return (parent, validated_token)
    
    
class RegisterStudentSerializer(serializers.Serializer):
    """
    Canonical registration contract shared by:

    - HTML Registration
    - Excel Import
    - CodeCamp Integration
    """

    first_name = serializers.CharField(
        max_length=100,
    )

    last_name = serializers.CharField(
        max_length=100,
        allow_blank=True,
        required=False,
    )

    date_of_birth = serializers.DateField(
        required=False,
        allow_null=True,
    )

    gender = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    class_name = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    batch = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    parent_title = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    parent_name = serializers.CharField(
        max_length=200,
    )

    parent_phone = serializers.CharField(
        max_length=20,
    )

    parent_whatsapp = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
    )

    parent_email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )

    relationship = serializers.CharField(
        required=False,
        allow_blank=True,
        default="Guardian",
    )

    photo = serializers.ImageField(
        required=False,
        allow_null=True,
    )

    mode = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    registration_code = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    camp_year = serializers.IntegerField(
        required=False,
    )

    program = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        class_name = (
            attrs.get("class_name")
            or attrs.get("batch")
            or ""
        ).strip()

        if not class_name:
            raise serializers.ValidationError(
                {
                    "class_name": (
                        "This field is required when batch is not provided."
                    )
                }
            )

        attrs["class_name"] = class_name

        if not attrs.get("relationship"):
            attrs["relationship"] = "Guardian"

        return attrs


class ParentChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    new_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=8,
    )

    confirm_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate(self, attrs):

        if (
            attrs["new_password"]
            != attrs["confirm_password"]
        ):
            raise serializers.ValidationError(
                {
                    "confirm_password": (
                        "Passwords do not match."
                    )
                }
            )

        return attrs

class ParentProfileSerializer(serializers.Serializer):

    title = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    full_name = serializers.CharField()

    email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )

    whatsapp_number = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    receive_email = serializers.BooleanField()

    receive_whatsapp = serializers.BooleanField()
