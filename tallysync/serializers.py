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
    total_pcs = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    items_summary = serializers.SerializerMethodField()

    class Meta:
        model = TallyInvoice
        exclude = ["raw_payload"]

    def get_pending_count(self, obj):
        return obj.pending_items.filter(resolved=False).count()

    def get_total_pcs(self, obj):
        try:
            payload = json.loads(obj.raw_payload or "{}")
            items = payload.get("items", [])
            return sum(int(item.get("qty", 0)) for item in items if item.get("qty"))
        except (json.JSONDecodeError, TypeError, ValueError):
            return 0

    def get_category(self, obj):
        try:
            payload = json.loads(obj.raw_payload or "{}")
            items = payload.get("items", [])
            text = (" ".join(item.get("name", "") for item in items) + " " + (obj.party_name or "")).lower()
            if "tube" in text or "tb" in text or "mld" in text or "jt" in text:
                return "tube"
            if "cycle" in text and "tyre" in text:
                return "cycletyre"
            if "tyre" in text or "tl" in text or "radial" in text or "nylon" in text:
                return "tyre"
            return "tyre"
        except Exception:
            return "all"

    def get_items_summary(self, obj):
        try:
            payload = json.loads(obj.raw_payload or "{}")
            items = payload.get("items", [])
            if not items:
                return ""
            names = [f"{item.get('name')} ({item.get('qty')} pcs)" for item in items if item.get('name')]
            return ", ".join(names[:3]) + (f" +{len(names)-3} more" if len(names) > 3 else "")
        except Exception:
            return ""


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
