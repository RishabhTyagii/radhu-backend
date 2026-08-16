from django.contrib import admin
from .models import CycleTyreItem, CycleTyreEntry, CycleTyreDailyManualEntry

@admin.register(CycleTyreItem)
class CycleTyreItemAdmin(admin.ModelAdmin):
    list_display = ["id", "size", "box_type", "material", "brand", "weight", "stock", "second_stock", "rfm_stock", "total_stock", "is_active", "created_at"]
    list_filter = ["is_active", "box_type", "material", "brand"]
    search_fields = ["size", "box_type", "material", "brand"]

@admin.register(CycleTyreEntry)
class CycleTyreEntryAdmin(admin.ModelAdmin):
    list_display = ["id", "tyre_item", "entry_type", "bucket", "quantity", "all_curing", "first_grade", "second_grade", "rejected_grade", "date", "bill_number", "user", "created_at"]
    list_filter = ["entry_type", "bucket", "date"]
    search_fields = ["tyre_item__size", "tyre_item__brand", "bill_number", "remark"]

@admin.register(CycleTyreDailyManualEntry)
class CycleTyreDailyManualEntryAdmin(admin.ModelAdmin):
    list_display = ["id", "date", "parchi_kg", "mixing_actual_compound", "chakka", "calander_bias_cutt", "packing_wastage", "tar", "updated_at"]
    list_filter = ["date"]
