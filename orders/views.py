from django.db import transaction
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Party, Order, OrderItem
from stock.models import TyreItem
from cycletube.models import CycleTubeItem
from cycletyres.models import CycleTyreItem
from .serializers import PartySerializer, OrderSerializer, OrderItemSerializer


def _build_stock_data(user):
    stock_data = []

    # Auto Tyre
    for item in TyreItem.objects.filter(is_active=True):
        my_qty = OrderItem.objects.filter(
            category='auto_tyre', tyre_item=item,
            order__user=user, order__status='pending'
        ).aggregate(s=Sum('quantity'))['s'] or 0

        other_qty = OrderItem.objects.filter(
            category='auto_tyre', tyre_item=item, order__status='pending'
        ).exclude(order__user=user).aggregate(s=Sum('quantity'))['s'] or 0

        stock_data.append({
            'category': 'auto_tyre',
            'category_label': 'Auto Tyre',
            'item_id': item.id,
            'display': f"{item.tyre} {item.pattern} {item.type}",
            'total_stock': item.stock,
            'my_orders': my_qty,
            'other_orders': other_qty,
            'available': item.stock - my_qty - other_qty,
        })

    # Cycle Tube
    for item in CycleTubeItem.objects.filter(is_active=True):
        my_qty = OrderItem.objects.filter(
            category='cycle_tube', tube_item=item,
            order__user=user, order__status='pending'
        ).aggregate(s=Sum('quantity'))['s'] or 0

        other_qty = OrderItem.objects.filter(
            category='cycle_tube', tube_item=item, order__status='pending'
        ).exclude(order__user=user).aggregate(s=Sum('quantity'))['s'] or 0

        stock_data.append({
            'category': 'cycle_tube',
            'category_label': 'Cycle Tube',
            'item_id': item.id,
            'display': f"{item.size} {item.type} {item.brand}",
            'total_stock': item.stock,
            'my_orders': my_qty,
            'other_orders': other_qty,
            'available': item.stock - my_qty - other_qty,
        })

    # Cycle Tyre
    for item in CycleTyreItem.objects.filter(is_active=True):
        my_qty = OrderItem.objects.filter(
            category='cycle_tyre', cycle_tyre_item=item,
            order__user=user, order__status='pending'
        ).aggregate(s=Sum('quantity'))['s'] or 0

        other_qty = OrderItem.objects.filter(
            category='cycle_tyre', cycle_tyre_item=item, order__status='pending'
        ).exclude(order__user=user).aggregate(s=Sum('quantity'))['s'] or 0

        stock_data.append({
            'category': 'cycle_tyre',
            'category_label': 'Cycle Tyre',
            'item_id': item.id,
            'display': f"{item.size} {item.box_type} {item.brand}",
            'total_stock': item.stock,
            'my_orders': my_qty,
            'other_orders': other_qty,
            'available': item.stock - my_qty - other_qty,
        })

    return stock_data


# Party Endpoints
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def party_list(request):
    if request.method == "GET":
        parties = Party.objects.filter(user=request.user)
        return Response(PartySerializer(parties, many=True).data)

    name = str(request.data.get("name", "")).strip()
    if not name:
        return Response({"error": "Party name is required"}, status=status.HTTP_400_BAD_REQUEST)

    party, created = Party.objects.get_or_create(user=request.user, name=name)
    return Response(PartySerializer(party).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def party_detail(request, pk):
    party = get_object_or_404(Party, pk=pk, user=request.user)
    party.delete()
    return Response({"ok": True})


# Stock Catalog for Order Booking
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stock_catalog(request):
    stock_data = _build_stock_data(request.user)
    return Response(stock_data)


# Order Endpoints
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def order_list(request):
    if request.method == "GET":
        is_admin = request.user.is_superuser or request.query_params.get("all") == "true"
        if is_admin:
            orders = Order.objects.all().select_related("user", "party", "resolved_by").prefetch_related("items")
        else:
            orders = Order.objects.filter(user=request.user).select_related("party", "resolved_by").prefetch_related("items")

        status_filter = request.query_params.get("status")
        if status_filter:
            orders = orders.filter(status=status_filter)

        return Response(OrderSerializer(orders, many=True).data)

    party_id = request.data.get("party_id")
    deadline = request.data.get("deadline") or None
    notes = str(request.data.get("notes", "")).strip()
    items = request.data.get("items", [])  # list of { category, item_id, quantity }

    if not party_id:
        return Response({"error": "party_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    party = get_object_or_404(Party, id=party_id, user=request.user)

    if not items or len(items) == 0:
        return Response({"error": "At least one item is required to place an order"}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        order = Order.objects.create(
            user=request.user,
            party=party,
            deadline=deadline,
            notes=notes or None,
            status="pending",
        )

        items_added = 0
        for it in items:
            cat = it.get("category")
            item_id = it.get("item_id")
            qty = int(it.get("quantity", 0))

            if qty <= 0 or not cat or not item_id:
                continue

            if cat == "auto_tyre":
                tyre = get_object_or_404(TyreItem, pk=item_id)
                OrderItem.objects.create(order=order, category=cat, tyre_item=tyre, quantity=qty)
                items_added += 1
            elif cat == "cycle_tube":
                tube = get_object_or_404(CycleTubeItem, pk=item_id)
                OrderItem.objects.create(order=order, category=cat, tube_item=tube, quantity=qty)
                items_added += 1
            elif cat == "cycle_tyre":
                ctyre = get_object_or_404(CycleTyreItem, pk=item_id)
                OrderItem.objects.create(order=order, category=cat, cycle_tyre_item=ctyre, quantity=qty)
                items_added += 1

        if items_added == 0:
            order.delete()
            return Response({"error": "No valid items found"}, status=status.HTTP_400_BAD_REQUEST)

    # Refetch with relations for proper serialization
    order = Order.objects.select_related("user", "party", "resolved_by").prefetch_related("items").get(pk=order.pk)
    return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def order_detail(request, pk):
    if request.user.is_superuser:
        order = get_object_or_404(
            Order.objects.select_related('user', 'party', 'resolved_by').prefetch_related('items'),
            pk=pk
        )
    else:
        order = get_object_or_404(
            Order.objects.select_related('user', 'party', 'resolved_by').prefetch_related('items'),
            pk=pk, user=request.user
        )

    if request.method == "GET":
        return Response(OrderSerializer(order).data)

    elif request.method == "DELETE":
        order.delete()
        return Response({"ok": True})

    new_status = request.data.get("status")
    if new_status and new_status in dict(Order.STATUS_CHOICES):
        order.status = new_status
        if new_status in ("completed", "cancelled"):
            order.resolved_by = request.user
            order.resolved_at = timezone.now()
        order.save()
        return Response(OrderSerializer(order).data)

    return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
