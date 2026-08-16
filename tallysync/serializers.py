from rest_framework import serializers
from .models import TallyItemMapping, TallyInvoice, TallySyncLog, TallyPendingItem
import json


class TallyItemMappingSerializer(serializers.ModelSerializer):
    module_display = serializers.CharField(source="get_module_display", read_only=True)
    item_label = serializers.SerializerMethodField()

    class Meta:
        model = TallyItemMapping
        fields = "__all__"

    def get_item_label(self, obj):
        item = obj.get_item()
        return str(item) if item else f"(deleted #{obj.item_id})"


class TallyInvoiceSerializer(serializers.ModelSerializer):
    gst_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    items = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()

    class Meta:
        model = TallyInvoice
        fields = "__all__"

    def get_items(self, obj):
        try:
            payload = json.loads(obj.raw_payload or "{}")
            return payload.get("items", [])
        except json.JSONDecodeError:
            return []

    def get_pending_count(self, obj):
        return obj.pending_items.filter(resolved=False).count()


class TallyInvoiceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views (no raw_payload)."""
    gst_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    pending_count = serializers.SerializerMethodField()

    class Meta:
        model = TallyInvoice
        exclude = ["raw_payload"]

    def get_pending_count(self, obj):
        return obj.pending_items.filter(resolved=False).count()


class TallySyncLogSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.voucher_number", default="", read_only=True)

    class Meta:
        model = TallySyncLog
        fields = "__all__"


class TallyPendingItemSerializer(serializers.ModelSerializer):
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    invoice_number = serializers.CharField(source="invoice.voucher_number", default="", read_only=True)

    class Meta:
        model = TallyPendingItem
        fields = "__all__"
