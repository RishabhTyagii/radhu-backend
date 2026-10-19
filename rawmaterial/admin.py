from django.contrib import admin
from .models import mixing_entry
# Register your models here.
@admin.register(mixing_entry) 
class mixing_entryAdmin(admin.ModelAdmin):
    list_display = ("date", "shift", "batch_no", "compound_name", "mixing_qty", "rubber_qty", "remarks")
    search_fields = ("date", "shift", "batch_no", "compound_name")
    list_filter = ("date", "shift", "compound_name")   