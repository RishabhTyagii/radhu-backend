from django.contrib import admin
from .models import TallyItemMapping, TallyInvoice, TallySyncLog, TallyPendingItem


@admin.register(TallyItemMapping)
class TallyItemMappingAdmin(admin.ModelAdmin):
    list_display = ("tally_item_name", "module", "item_id", "created_at")
    search_fields = ("tally_item_name",)
    list_filter = ("module",)


@admin.register(TallyInvoice)
class TallyInvoiceAdmin(admin.ModelAdmin):
    list_display = ("voucher_number", "voucher_date", "party_name", "total_value", "gst_total", "stock_synced")
    search_fields = ("voucher_number", "party_name")
    list_filter = ("stock_synced", "voucher_date")


@admin.register(TallySyncLog)
class TallySyncLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "level", "invoice", "message")
    list_filter = ("level",)


@admin.register(TallyPendingItem)
class TallyPendingItemAdmin(admin.ModelAdmin):
    list_display = ("tally_item_name", "qty", "reason", "voucher_number", "resolved", "created_at")
    list_filter = ("reason", "resolved")
    search_fields = ("tally_item_name", "voucher_number")
