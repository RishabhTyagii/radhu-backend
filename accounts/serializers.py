from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, PAGES_MAP


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['allowed_pages']


class UserSerializer(serializers.ModelSerializer):
    allowed_pages = serializers.SerializerMethodField()
    is_superuser = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'is_superuser', 'is_active', 'date_joined', 'allowed_pages']

    def get_allowed_pages(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.allowed_pages if profile else []
