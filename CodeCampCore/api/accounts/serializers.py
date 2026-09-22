from rest_framework import serializers
from django.contrib.auth.models import User
from apps.accounts.models import Profile


class ProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = Profile
        fields = [
            "phone",
            "is_verified",
            "onboarding_stage",
        ]


class UserSerializer(serializers.ModelSerializer):

    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "profile",
        ]