from django.contrib import admin
from .models import CycleTubeItem, CycleTubeEntry, CycleTubeDailyManualEntry

@admin.register(CycleTubeItem)
class CycleTubeItemAdmin(admin.ModelAdmin):
    list_display = ["id", "size", "type", "brand", "weight", "stock", "rfm_stock", "total_stock", "is_active", "created_at"]
    list_filter = ["is_active", "type", "brand"]
    search_fields = ["size", "type", "brand"]
    ordering = ["size", "type", "brand"]

@admin.register(CycleTubeEntry)
class CycleTubeEntryAdmin(admin.ModelAdmin):
    list_display = ["id", "tube_item", "entry_type", "bucket", "quantity", "tube_quality", "date", "bill_number", "user", "created_at"]
    list_filter = ["entry_type", "bucket", "tube_quality", "date"]
    search_fields = ["tube_item__size", "tube_item__type", "tube_item__brand", "bill_number", "remark"]
    ordering = ["-date", "-created_at"]

@admin.register(CycleTubeDailyManualEntry)
class CycleTubeDailyManualEntryAdmin(admin.ModelAdmin):
    list_display = ["id", "date", "valve_body_issued", "actual_wt_gross", "actual_mixing_compound", "total_tube_waste", "updated_at"]
    list_filter = ["date"]
    ordering = ["-date"]
