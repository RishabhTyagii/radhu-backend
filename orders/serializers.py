from rest_framework import serializers
from .models import Party, Order, OrderItem


class PartySerializer(serializers.ModelSerializer):
    class Meta:
        model = Party
        fields = ['id', 'user', 'name', 'created_at']


class OrderItemSerializer(serializers.ModelSerializer):
    item_display = serializers.CharField(read_only=True)
    item_stock = serializers.IntegerField(read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'category', 'tyre_item', 'tube_item',
                  'cycle_tyre_item', 'quantity', 'price', 'subtotal', 'item_display', 'item_stock']

    def get_subtotal(self, obj):
        return float(obj.quantity * obj.price)


class OrderSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    total_quantity = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'user', 'user_name', 'party', 'party_name', 'date',
                  'deadline', 'status', 'status_display', 'notes', 'is_overdue',
                  'resolved_by', 'resolved_by_name', 'resolved_at', 'created_at',
                  'items', 'total_quantity', 'total_amount']

    def get_total_quantity(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_total_amount(self, obj):
        return sum(float(item.quantity * item.price) for item in obj.items.all())

    def get_resolved_by_name(self, obj):
        return obj.resolved_by.username if obj.resolved_by else None
