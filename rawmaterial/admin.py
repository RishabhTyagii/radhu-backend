from django.contrib import admin
from .models import MixingEntry, MaterialGroup, Material, StockEntry

@admin.register(MaterialGroup)
class MaterialGroupAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "unit", "minimum_stock")
    list_filter = ("group",)
    search_fields = ("name",)

@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "material", "opening", "received_quantity", "used_quantity", "closing", "created_by")
    list_filter = ("material__group", "date")
    search_fields = ("material__name",)
    ordering = ("-date",)

@admin.register(MixingEntry)
class MixingEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "compound_total", "rubber_total", "diff", "rubber_bdls", "rubber_kgs", "updated_at")
    search_fields = ("date", "notes")
    list_filter = ("date",)
    ordering = ("-date",)