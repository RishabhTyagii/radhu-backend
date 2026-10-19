from django.contrib import admin
from .models import MixingEntry

@admin.register(MixingEntry)
class MixingEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "compound_total", "rubber_total", "diff", "rubber_bdls", "rubber_kgs", "updated_at")
    search_fields = ("date", "notes")
    list_filter = ("date",)
    ordering = ("-date",)