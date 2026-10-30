from rest_framework import serializers
from .models import CycleTyreItem, CycleTyreEntry, CycleTyreDailyManualEntry

class CycleTyreItemSerializer(serializers.ModelSerializer):
    total_stock = serializers.ReadOnlyField()

    class Meta:
        model = CycleTyreItem
        fields = [
            "id", "sku", "box_type", "size", "material", "brand", "weight",
            "stock", "second_stock", "rfm_stock", "total_stock", "is_active", "created_at"
        ]

class CycleTyreEntrySerializer(serializers.ModelSerializer):
    tyre_item_detail = CycleTyreItemSerializer(source="tyre_item", read_only=True)
    bucket_display = serializers.CharField(source="get_bucket_display", read_only=True)
    user_username = serializers.ReadOnlyField(source="user.username")
    linked_employee_name = serializers.SerializerMethodField()

    class Meta:
        model = CycleTyreEntry
        fields = [
            "id", "tyre_item", "tyre_item_detail", "entry_type", "bucket",
            "bucket_display", "quantity", "all_curing", "first_grade", "second_grade",
            "rejected_grade", "date", "bill_number", "remark", "user", "user_username",
            "linked_employee_id", "linked_employee_name", "created_at"
        ]
        read_only_fields = ["user", "created_at"]

    def get_linked_employee_name(self, obj):
        if not obj.linked_employee_id:
            return None
        try:
            from hrms.models import Employee
            emp = Employee.objects.get(pk=obj.linked_employee_id)
            return emp.name
        except Exception:
            return None

class CycleTyreDailyManualEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CycleTyreDailyManualEntry
        fields = [
            "id", "date", "packing_pcs", "parchi_kg", "mixing_actual_compound", "chakka",
            "calander_bias_cutt", "packing_wastage", "tar", "updated_at"
        ]
