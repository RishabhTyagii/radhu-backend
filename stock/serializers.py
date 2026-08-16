from rest_framework import serializers
from .models import TyreItem, DailyEntry, DailyProductionManualEntry

class TyreItemSerializer(serializers.ModelSerializer):
    total_stock = serializers.ReadOnlyField()
    class Meta:
        model = TyreItem
        fields = "__all__"

class DailyEntrySerializer(serializers.ModelSerializer):
    tyre_item = TyreItemSerializer(read_only=True)
    entry_type_display = serializers.CharField(source="get_entry_type_display", read_only=True)
    bucket_display = serializers.CharField(source="get_bucket_display", read_only=True)
    user_display = serializers.CharField(source="user.username", read_only=True, allow_null=True)

    class Meta:
        model = DailyEntry
        fields = "__all__"

class DailyProductionManualEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyProductionManualEntry
        fields = "__all__"
