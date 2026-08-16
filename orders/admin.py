from django.contrib import admin
from .models import Party, Order, OrderItem

@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    search_fields = ("name", "user__username")

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "party", "date", "deadline", "status", "created_at")
    list_filter = ("status", "date")
    search_fields = ("party__name", "user__username")
    inlines = [OrderItemInline]
