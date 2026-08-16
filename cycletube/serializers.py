from rest_framework import serializers
from .models import CycleTubeItem, CycleTubeEntry, CycleTubeDailyManualEntry

class CycleTubeItemSerializer(serializers.ModelSerializer):
    total_stock = serializers.ReadOnlyField()

    class Meta:
        model = CycleTubeItem
        fields = [
            "id",
            "size",
            "type",
            "brand",
            "weight",
            "stock",
            "rfm_stock",
            "total_stock",
            "is_active",
            "created_at",
        ]

class CycleTubeEntrySerializer(serializers.ModelSerializer):
    tube_item_detail = CycleTubeItemSerializer(source="tube_item", read_only=True)
    user_username = serializers.ReadOnlyField(source="user.username")

    class Meta:
        model = CycleTubeEntry
        fields = [
            "id",
            "tube_item",
            "tube_item_detail",
            "entry_type",
            "bucket",
            "quantity",
            "tube_quality",
            "date",
            "bill_number",
            "remark",
            "user",
            "user_username",
            "created_at",
        ]
        read_only_fields = ["user", "created_at"]

class CycleTubeDailyManualEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CycleTubeDailyManualEntry
        fields = [
            "id",
            "date",
            "valve_body_issued",
            "actual_wt_gross",
            "actual_mixing_compound",
            "jali",
            "die_wastage",
            "tube_cutting",
            "total_tube_waste",
            "updated_at",
        ]
