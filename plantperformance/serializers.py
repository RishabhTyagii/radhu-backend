from rest_framework import serializers
from .models import PlantPerformanceDailyLog


class PlantPerformanceDailyLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlantPerformanceDailyLog
        fields = "__all__"
