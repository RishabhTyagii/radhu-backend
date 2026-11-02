import re
import datetime
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    CycleTubeItem,
    CycleTubeEntry,
    CycleTubeDailyManualEntry,
    PACK_FACTOR,
    VB_FACTOR,
    COMB_FACTOR,
)
from .serializers import (
    CycleTubeItemSerializer,
    CycleTubeEntrySerializer,
    CycleTubeDailyManualEntrySerializer,
)


def _recalculate_tube_stocks():
    for item in CycleTubeItem.objects.all():
        p_stock = CycleTubeEntry.objects.filter(tube_item=item, entry_type='production', bucket='stock').aggregate(t=Sum('quantity'))['t'] or 0
        s_stock = CycleTubeEntry.objects.filter(tube_item=item, entry_type='sale', bucket='stock').aggregate(t=Sum('quantity'))['t'] or 0
        a_stock = CycleTubeEntry.objects.filter(tube_item=item, entry_type='adjustment', bucket='stock').aggregate(t=Sum('quantity'))['t'] or 0

        p_rfm = CycleTubeEntry.objects.filter(tube_item=item, entry_type='production', bucket='rfm_stock').aggregate(t=Sum('quantity'))['t'] or 0
        s_rfm = CycleTubeEntry.objects.filter(tube_item=item, entry_type='sale', bucket='rfm_stock').aggregate(t=Sum('quantity'))['t'] or 0
        a_rfm = CycleTubeEntry.objects.filter(tube_item=item, entry_type='adjustment', bucket='rfm_stock').aggregate(t=Sum('quantity'))['t'] or 0

        item.stock = p_stock - s_stock + a_stock
        item.rfm_stock = p_rfm - s_rfm + a_rfm
        item.save(update_fields=['stock', 'rfm_stock'])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    """
    Dashboard API: Returns items list with previous closing, month_production, month_sale,
    closing_stock, isolated rfm_stock, and total_stock per item, with month and custom date range filters.
    """
    _recalculate_tube_stocks()

    today = datetime.date.today()
    start_date_param = request.query_params.get("start_date", "").strip()
    end_date_param = request.query_params.get("end_date", "").strip()
    month_param = request.query_params.get("month", "").strip()

    filter_start = None
    filter_end = None
    is_filtered_range = False

    if start_date_param and end_date_param:
        try:
            filter_start = datetime.datetime.strptime(start_date_param, "%Y-%m-%d").date()
            filter_end = datetime.datetime.strptime(end_date_param, "%Y-%m-%d").date()
            is_filtered_range = True
        except ValueError:
            pass

    if not is_filtered_range:
        if not month_param:
            month_param = f"{today.year}-{today.month:02d}"

        if month_param != "all":
            try:
                parts = month_param.split("-")
                year, month = int(parts[0]), int(parts[1])
                filter_start = datetime.date(year, month, 1)
                if month == 12:
                    filter_end = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
                else:
                    filter_end = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
                is_filtered_range = True
            except (ValueError, IndexError):
                month_param = "all"
                is_filtered_range = False

    # Stats calculation for today
    today_prod = (
        CycleTubeEntry.objects.filter(date=today, entry_type="production", bucket="stock").aggregate(
            total=Sum("quantity")
        )["total"]
        or 0
    )

    today_sale = (
        CycleTubeEntry.objects.filter(date=today, entry_type="sale", bucket="stock").aggregate(
            total=Sum("quantity")
        )["total"]
        or 0
    )

    active_items = CycleTubeItem.objects.filter(is_active=True)
    items_data = []

    tot_prev_closing = 0
    tot_month_prod = 0
    tot_month_sale = 0
    tot_closing_stock = 0
    tot_rfm_stock = 0
    tot_total_stock = 0

    for item in active_items:
        if is_filtered_range and filter_start and filter_end:
            # Prior closing before start date (main stock only)
            p_prev = CycleTubeEntry.objects.filter(
                tube_item=item, entry_type="production", bucket="stock", date__lt=filter_start
            ).aggregate(t=Sum("quantity"))["t"] or 0
            s_prev = CycleTubeEntry.objects.filter(
                tube_item=item, entry_type="sale", bucket="stock", date__lt=filter_start
            ).aggregate(t=Sum("quantity"))["t"] or 0
            a_prev = CycleTubeEntry.objects.filter(
                tube_item=item, entry_type="adjustment", bucket="stock", date__lt=filter_start
            ).aggregate(t=Sum("quantity"))["t"] or 0

            prev_closing = p_prev - s_prev + a_prev

            # In-range production and sales (strictly main stock, RFM isolated)
            month_prod = CycleTubeEntry.objects.filter(
                tube_item=item, entry_type="production", bucket="stock", date__gte=filter_start, date__lte=filter_end
            ).aggregate(t=Sum("quantity"))["t"] or 0

            month_sale = CycleTubeEntry.objects.filter(
                tube_item=item, entry_type="sale", bucket="stock", date__gte=filter_start, date__lte=filter_end
            ).aggregate(t=Sum("quantity"))["t"] or 0

            month_adj = CycleTubeEntry.objects.filter(
                tube_item=item, entry_type="adjustment", bucket="stock", date__gte=filter_start, date__lte=filter_end
            ).aggregate(t=Sum("quantity"))["t"] or 0

            closing_stock = prev_closing + month_prod - month_sale + month_adj
            rfm = item.rfm_stock
            total_stock_item = closing_stock + rfm

        else:
            # All time
            prev_closing = 0

            month_prod = CycleTubeEntry.objects.filter(
                tube_item=item, entry_type="production", bucket="stock"
            ).aggregate(t=Sum("quantity"))["t"] or 0

            month_sale = CycleTubeEntry.objects.filter(
                tube_item=item, entry_type="sale", bucket="stock"
            ).aggregate(t=Sum("quantity"))["t"] or 0

            closing_stock = item.stock
            rfm = item.rfm_stock
            total_stock_item = closing_stock + rfm

        serialized = CycleTubeItemSerializer(item).data
        serialized.update({
            "prev_closing": prev_closing,
            "month_production": month_prod,
            "month_sale": month_sale,
            "closing_stock": closing_stock,
            "rfm_stock": rfm,
            "total_stock": total_stock_item,
        })
        items_data.append(serialized)

        tot_prev_closing += prev_closing
        tot_month_prod += month_prod
        tot_month_sale += month_sale
        tot_closing_stock += closing_stock
        tot_rfm_stock += rfm
        tot_total_stock += total_stock_item

    # Dynamic available months
    entry_dates = CycleTubeEntry.objects.dates("date", "month", order="DESC")
    month_set = set()
    available_months = [{"value": "all", "label": "All Time / Overall"}]

    standard_months = [
        ("2026-08", "August 2026"),
        ("2026-07", "July 2026"),
        ("2026-06", "June 2026"),
        ("2026-05", "May 2026"),
        ("2026-04", "April 2026"),
    ]
    for val, lbl in standard_months:
        available_months.append({"value": val, "label": lbl})
        month_set.add(val)

    for ed in entry_dates:
        val = f"{ed.year}-{ed.month:02d}"
        if val not in month_set:
            lbl = ed.strftime("%B %Y")
            available_months.append({"value": val, "label": lbl})
            month_set.add(val)

    return Response({
        "selected_month": month_param or "custom",
        "start_date": str(filter_start) if filter_start else None,
        "end_date": str(filter_end) if filter_end else None,
        "available_months": available_months,
        "stats": {
            "today_production": today_prod,
            "today_sale": today_sale,
            "month_production": tot_month_prod,
            "month_sale": tot_month_sale,
            "closing_stock": tot_closing_stock,
            "rfm_stock": tot_rfm_stock,
            "total_stock": tot_total_stock,
        },
        "totals": {
            "prev_closing": tot_prev_closing,
            "month_production": tot_month_prod,
            "month_sale": tot_month_sale,
            "closing_stock": tot_closing_stock,
            "rfm_stock": tot_rfm_stock,
            "total_stock": tot_total_stock,
        },
        "items": items_data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_item(request):
    """
    Create a new CycleTubeItem.
    """
    serializer = CycleTubeItemSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def add_production(request):
    """
    GET: Returns list of active items and 15 recent production entries.
    POST: Adds quantity to item's stock/rfm_stock bucket and records production entry.
    """
    if request.method == "GET":
        items = CycleTubeItem.objects.filter(is_active=True)
        recent_entries = CycleTubeEntry.objects.filter(entry_type="production")[:15]
        return Response(
            {
                "items": CycleTubeItemSerializer(items, many=True).data,
                "recent_entries": CycleTubeEntrySerializer(recent_entries, many=True).data,
            }
        )

    # POST logic
    tube_item_id = request.data.get("tube_item")
    quantity = request.data.get("quantity")
    bucket = request.data.get("bucket", "stock")
    tube_quality = request.data.get("tube_quality", "normal")
    date_val = request.data.get("date", str(datetime.date.today()))
    remark = request.data.get("remark", "")

    if not tube_item_id or quantity is None:
        return Response(
            {"error": "tube_item and quantity are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        quantity = int(quantity)
        if quantity <= 0:
            return Response(
                {"error": "Quantity must be greater than 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid quantity format."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tube_item = get_object_or_404(CycleTubeItem, pk=tube_item_id)

    # Update item stock bucket
    if bucket == "rfm_stock":
        tube_item.rfm_stock += quantity
    else:
        tube_item.stock += quantity
    tube_item.save()

    entry = CycleTubeEntry.objects.create(
        tube_item=tube_item,
        entry_type="production",
        bucket=bucket,
        quantity=quantity,
        tube_quality=tube_quality,
        date=date_val,
        remark=remark,
        user=request.user if request.user.is_authenticated else None,
    )

    return Response(CycleTubeEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def add_sale(request):
    """
    GET: Returns list of active items and 15 recent sale entries.
    POST: Validates bill_number duplicate, checks stock availability, subtracts from bucket.
    """
    if request.method == "GET":
        items = CycleTubeItem.objects.filter(is_active=True)
        recent_entries = CycleTubeEntry.objects.filter(entry_type="sale")[:15]
        return Response(
            {
                "items": CycleTubeItemSerializer(items, many=True).data,
                "recent_entries": CycleTubeEntrySerializer(recent_entries, many=True).data,
            }
        )

    # POST logic
    tube_item_id = request.data.get("tube_item")
    quantity = request.data.get("quantity")
    bucket = request.data.get("bucket", "stock")
    tube_quality = request.data.get("tube_quality", "normal")
    date_val = request.data.get("date", str(datetime.date.today()))
    bill_number = request.data.get("bill_number", "").strip()
    remark = request.data.get("remark", "")

    if not tube_item_id or quantity is None:
        return Response(
            {"error": "tube_item and quantity are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        quantity = int(quantity)
        if quantity <= 0:
            return Response(
                {"error": "Quantity must be greater than 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid quantity format."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check bill_number duplicate if provided
    if bill_number:
        if CycleTubeEntry.objects.filter(bill_number=bill_number, entry_type="sale").exists():
            return Response(
                {"error": f"Bill number '{bill_number}' already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    tube_item = get_object_or_404(CycleTubeItem, pk=tube_item_id)

    # Check stock availability
    available_stock = tube_item.rfm_stock if bucket == "rfm_stock" else tube_item.stock
    if quantity > available_stock:
        return Response(
            {
                "error": f"Insufficient stock in '{bucket}'. Available: {available_stock}, Requested: {quantity}."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Subtract from bucket
    if bucket == "rfm_stock":
        tube_item.rfm_stock -= quantity
    else:
        tube_item.stock -= quantity
    tube_item.save()

    entry = CycleTubeEntry.objects.create(
        tube_item=tube_item,
        entry_type="sale",
        bucket=bucket,
        quantity=quantity,
        tube_quality=tube_quality,
        date=date_val,
        bill_number=bill_number,
        remark=remark,
        user=request.user if request.user.is_authenticated else None,
    )

    return Response(CycleTubeEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def add_adjustment(request):
    """
    GET: Returns list of active items and 15 recent adjustment entries.
    POST: Add or subtract stock quantity with validation against negative stock.
    """
    if request.method == "GET":
        items = CycleTubeItem.objects.filter(is_active=True)
        recent_entries = CycleTubeEntry.objects.filter(entry_type="adjustment")[:15]
        return Response(
            {
                "items": CycleTubeItemSerializer(items, many=True).data,
                "recent_entries": CycleTubeEntrySerializer(recent_entries, many=True).data,
            }
        )

    tube_item_id = request.data.get("tube_item")
    quantity = request.data.get("quantity")
    bucket = request.data.get("bucket", "stock")
    date_val = request.data.get("date", str(datetime.date.today()))
    remark = request.data.get("remark", "")

    if not tube_item_id or quantity is None:
        return Response(
            {"error": "tube_item and quantity are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid quantity format."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tube_item = get_object_or_404(CycleTubeItem, pk=tube_item_id)

    curr_stock = tube_item.rfm_stock if bucket == "rfm_stock" else tube_item.stock
    if quantity < 0 and (curr_stock + quantity < 0):
        return Response(
            {
                "error": f"Adjustment would result in negative stock in '{bucket}'. Current: {curr_stock}, Adjustment: {quantity}."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if bucket == "rfm_stock":
        tube_item.rfm_stock += quantity
    else:
        tube_item.stock += quantity
    tube_item.save()

    entry = CycleTubeEntry.objects.create(
        tube_item=tube_item,
        entry_type="adjustment",
        bucket=bucket,
        quantity=quantity,
        date=date_val,
        remark=remark,
        user=request.user if request.user.is_authenticated else None,
    )

    return Response(CycleTubeEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def entries_log(request):
    """
    Log of entries filtered by date, month, entry_type, bucket, tube_item, tube_quality.
    """
    qs = CycleTubeEntry.objects.select_related("tube_item", "user").all()

    date_param = request.query_params.get("date")
    month_param = request.query_params.get("month")  # format YYYY-MM
    entry_type = request.query_params.get("entry_type")
    bucket = request.query_params.get("bucket")
    tube_item_id = request.query_params.get("tube_item")
    tube_quality = request.query_params.get("tube_quality")

    if date_param:
        qs = qs.filter(date=date_param)
    elif month_param:
        try:
            parts = month_param.split("-")
            qs = qs.filter(date__year=int(parts[0]), date__month=int(parts[1]))
        except (ValueError, IndexError):
            pass

    if entry_type and entry_type != "all":
        qs = qs.filter(entry_type=entry_type)

    if bucket and bucket != "all":
        qs = qs.filter(bucket=bucket)

    if tube_item_id:
        qs = qs.filter(tube_item_id=tube_item_id)

    if tube_quality and tube_quality != "all":
        qs = qs.filter(tube_quality=tube_quality)

    return Response(CycleTubeEntrySerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_report(request):
    """
    Monthly production and sale report per item.
    """
    today = datetime.date.today()
    year_param = request.query_params.get("year", today.year)
    month_param = request.query_params.get("month", today.month)

    try:
        year = int(year_param)
        month = int(month_param)
    except (ValueError, TypeError):
        year = today.year
        month = today.month

    items = CycleTubeItem.objects.filter(is_active=True)
    report_items = []

    total_monthly_prod = 0
    total_monthly_sale = 0
    total_stock = 0
    total_rfm_stock = 0

    for item in items:
        prod_qty = (
            CycleTubeEntry.objects.filter(
                tube_item=item,
                entry_type="production",
                date__year=year,
                date__month=month,
            ).exclude(bucket="rfm_stock").aggregate(total=Sum("quantity"))["total"]
            or 0
        )

        sale_qty = (
            CycleTubeEntry.objects.filter(
                tube_item=item,
                entry_type="sale",
                date__year=year,
                date__month=month,
            ).aggregate(total=Sum("quantity"))["total"]
            or 0
        )

        report_items.append(
            {
                "id": item.id,
                "size": item.size,
                "type": item.type,
                "brand": item.brand,
                "weight": str(item.weight),
                "stock": item.stock,
                "rfm_stock": item.rfm_stock,
                "total_stock": item.total_stock,
                "monthly_production": prod_qty,
                "monthly_sale": sale_qty,
            }
        )

        total_monthly_prod += prod_qty
        total_monthly_sale += sale_qty
        total_stock += item.stock
        total_rfm_stock += item.rfm_stock

    return Response(
        {
            "year": year,
            "month": month,
            "items": report_items,
            "totals": {
                "total_monthly_production": total_monthly_prod,
                "total_monthly_sale": total_monthly_sale,
                "total_stock": total_stock,
                "total_rfm_stock": total_rfm_stock,
            },
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def production_summary(request):
    """
    Production Summary report with auto-calculated columns using PACK_FACTOR, VB_FACTOR, COMB_FACTOR.
    GET: Returns auto-calculated daily rows + totals for requested month/date range.
    POST: Saves/updates CycleTubeDailyManualEntry.
    """
    if request.method == "POST":
        date_val = request.data.get("date")
        if not date_val:
            return Response(
                {"error": "date field is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        def to_dec(val):
            try:
                return Decimal(str(val)) if val is not None else Decimal("0.00")
            except Exception:
                return Decimal("0.00")

        manual_entry, created = CycleTubeDailyManualEntry.objects.update_or_create(
            date=date_val,
            defaults={
                "valve_body_issued": to_dec(request.data.get("valve_body_issued")),
                "actual_wt_gross": to_dec(request.data.get("actual_wt_gross")),
                "actual_mixing_compound": to_dec(request.data.get("actual_mixing_compound")),
                "jali": to_dec(request.data.get("jali")),
                "die_wastage": to_dec(request.data.get("die_wastage")),
                "tube_cutting": to_dec(request.data.get("tube_cutting")),
                "total_tube_waste": to_dec(request.data.get("total_tube_waste")),
            },
        )
        return Response(
            CycleTubeDailyManualEntrySerializer(manual_entry).data,
            status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED,
        )

    # GET logic
    today = datetime.date.today()
    month_param = request.query_params.get("month")  # format YYYY-MM
    start_date_param = request.query_params.get("start_date")
    end_date_param = request.query_params.get("end_date")

    if start_date_param and end_date_param:
        try:
            start_date = datetime.datetime.strptime(start_date_param, "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(end_date_param, "%Y-%m-%d").date()
        except ValueError:
            start_date = today.replace(day=1)
            end_date = today
    elif month_param:
        try:
            parts = month_param.split("-")
            year_val, month_val = int(parts[0]), int(parts[1])
            start_date = datetime.date(year_val, month_val, 1)
            # Find last day of month
            if month_val == 12:
                end_date = datetime.date(year_val, 12, 31)
            else:
                end_date = datetime.date(year_val, month_val + 1, 1) - datetime.timedelta(days=1)
        except (ValueError, IndexError):
            start_date = today.replace(day=1)
            end_date = today
    else:
        start_date = today.replace(day=1)
        end_date = today

    # Find all distinct dates within date range from entries or manual entries
    entry_dates = set(
        CycleTubeEntry.objects.filter(
            date__gte=start_date, date__lte=end_date, entry_type="production"
        ).exclude(bucket="rfm_stock").values_list("date", flat=True)
    )
    manual_dates = set(
        CycleTubeDailyManualEntry.objects.filter(
            date__gte=start_date, date__lte=end_date
        ).values_list("date", flat=True)
    )
    all_dates = sorted(list(entry_dates.union(manual_dates)), reverse=True)

    summary_rows = []
    tot_pcs = 0
    tot_target_wt = Decimal("0.0000")
    tot_actual_wt_gross = Decimal("0.00")
    tot_actual_wt_net = Decimal("0.0000")
    tot_variance_wt = Decimal("0.0000")
    tot_target_consmpt = Decimal("0.0000")
    tot_actual_comp_net = Decimal("0.0000")
    tot_variance_comp = Decimal("0.0000")
    tot_actual_mixing = Decimal("0.00")
    tot_variance_mixing = Decimal("0.0000")
    tot_valve_body_issued = Decimal("0.00")
    tot_jali = Decimal("0.00")
    tot_die_wastage = Decimal("0.00")
    tot_tube_cutting = Decimal("0.00")
    tot_total_tube_waste = Decimal("0.00")

    for d in all_dates:
        prod_entries = CycleTubeEntry.objects.filter(
            date=d, entry_type="production"
        ).exclude(bucket="rfm_stock").select_related("tube_item")

        pcs = sum(e.quantity for e in prod_entries)
        target_wt = sum(
            (e.tube_item.weight if e.tube_item else Decimal("0")) * Decimal(e.quantity)
            for e in prod_entries
        )

        manual = CycleTubeDailyManualEntry.objects.filter(date=d).first()
        actual_wt_gross = manual.actual_wt_gross if manual else Decimal("0.00")
        actual_mixing_compound = manual.actual_mixing_compound if manual else Decimal("0.00")
        valve_body_issued = manual.valve_body_issued if manual else Decimal("0.00")
        jali = manual.jali if manual else Decimal("0.00")
        die_wastage = manual.die_wastage if manual else Decimal("0.00")
        tube_cutting = manual.tube_cutting if manual else Decimal("0.00")
        total_tube_waste = manual.total_tube_waste if manual else Decimal("0.00")

        pcs_dec = Decimal(pcs)
        actual_wt_net = actual_wt_gross - (pcs_dec * PACK_FACTOR)
        variance_wt = actual_wt_net - target_wt
        target_consmpt = target_wt - (pcs_dec * VB_FACTOR)
        actual_comp_net = actual_wt_gross - (pcs_dec * COMB_FACTOR)
        variance_comp = actual_comp_net - target_consmpt
        variance_mixing = actual_mixing_compound - target_consmpt

        row = {
            "date": str(d),
            "pcs": pcs,
            "target_wt": round(target_wt, 4),
            "actual_wt_gross": round(actual_wt_gross, 2),
            "actual_wt_net": round(actual_wt_net, 4),
            "variance_wt": round(variance_wt, 4),
            "target_consmpt": round(target_consmpt, 4),
            "actual_comp_net": round(actual_comp_net, 4),
            "variance_comp": round(variance_comp, 4),
            "actual_mixing_compound": round(actual_mixing_compound, 2),
            "variance_mixing": round(variance_mixing, 4),
            "valve_body_issued": round(valve_body_issued, 2),
            "jali": round(jali, 2),
            "die_wastage": round(die_wastage, 2),
            "tube_cutting": round(tube_cutting, 2),
            "total_tube_waste": round(total_tube_waste, 2),
            "manual_entry_id": manual.id if manual else None,
        }
        summary_rows.append(row)

        tot_pcs += pcs
        tot_target_wt += target_wt
        tot_actual_wt_gross += actual_wt_gross
        tot_actual_wt_net += actual_wt_net
        tot_variance_wt += variance_wt
        tot_target_consmpt += target_consmpt
        tot_actual_comp_net += actual_comp_net
        tot_variance_comp += variance_comp
        tot_actual_mixing += actual_mixing_compound
        tot_variance_mixing += variance_mixing
        tot_valve_body_issued += valve_body_issued
        tot_jali += jali
        tot_die_wastage += die_wastage
        tot_tube_cutting += tube_cutting
        tot_total_tube_waste += total_tube_waste

    totals = {
        "pcs": tot_pcs,
        "target_wt": round(tot_target_wt, 4),
        "actual_wt_gross": round(tot_actual_wt_gross, 2),
        "actual_wt_net": round(tot_actual_wt_net, 4),
        "variance_wt": round(tot_variance_wt, 4),
        "target_consmpt": round(tot_target_consmpt, 4),
        "actual_comp_net": round(tot_actual_comp_net, 4),
        "variance_comp": round(tot_variance_comp, 4),
        "actual_mixing_compound": round(tot_actual_mixing, 2),
        "variance_mixing": round(tot_variance_mixing, 4),
        "valve_body_issued": round(tot_valve_body_issued, 2),
        "jali": round(tot_jali, 2),
        "die_wastage": round(tot_die_wastage, 2),
        "tube_cutting": round(tot_tube_cutting, 2),
        "total_tube_waste": round(tot_total_tube_waste, 2),
    }

    return Response(
        {
            "start_date": str(start_date),
            "end_date": str(end_date),
            "summary": summary_rows,
            "totals": totals,
        }
    )


def sku_sort_key(sku, fallback=""):
    """
    Sorts codes alphanumerically like CTB1..CTB45, CTBRFM1, CTBRJ1, etc.
    Items without code go to the end, ordered alphabetically by fallback.
    """
    if not sku:
        return (1, 9999, str(fallback or "").upper())
    sku_str = str(sku).strip().upper()
    m = re.match(r"^([A-Z]+)(\d+)(.*)$", sku_str)
    if m:
        prefix, num, suffix = m.groups()
        order = 0
        if any(x in prefix for x in ["RJ", "RS", "RFM"]):
            order = 2
        return (order, prefix, int(num), suffix)
    if sku_str.isdigit():
        return (0, "", int(sku_str), "")
    return (0, sku_str, 0, "")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def production_sheet(request):
    """
    Date-wise production sheet for Cycle Tube.
    Returns items with dates_data {date: {normal, molded, second, total}} for Excel export.
    """
    today = datetime.date.today()
    date_param = request.query_params.get("date")
    month_param = request.query_params.get("month")

    if date_param:
        try:
            target_date = datetime.datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            target_date = today
        entries = CycleTubeEntry.objects.filter(entry_type="production", date=target_date).exclude(bucket="rfm_stock").select_related("tube_item")
    elif month_param:
        try:
            parts = month_param.split("-")
            year, month = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            year, month = today.year, today.month
        entries = CycleTubeEntry.objects.filter(entry_type="production", date__year=year, date__month=month).exclude(bucket="rfm_stock").select_related("tube_item")
    else:
        entries = CycleTubeEntry.objects.filter(entry_type="production", date__year=today.year, date__month=today.month).exclude(bucket="rfm_stock").select_related("tube_item")

    item_map = {}
    for e in entries:
        tid = e.tube_item.id
        if tid not in item_map:
            item_map[tid] = {
                "id": tid,
                "sku": e.tube_item.sku or "",
                "tube_name": f"{e.tube_item.size} {e.tube_item.type} {e.tube_item.brand}".strip(),
                "size": e.tube_item.size or "",
                "type": e.tube_item.type or "",
                "brand": e.tube_item.brand or "",
                "weight": float(e.tube_item.weight or 0.950),
                "dates_data": {},
            }

        date_str = str(e.date)
        if date_str not in item_map[tid]["dates_data"]:
            item_map[tid]["dates_data"][date_str] = {"normal": 0, "molded": 0, "second": 0, "total": 0}

        q = e.quantity or 0
        quality = e.tube_quality or "normal"
        if quality == "molded":
            item_map[tid]["dates_data"][date_str]["molded"] += q
        elif quality == "second":
            item_map[tid]["dates_data"][date_str]["second"] += q
        else:
            item_map[tid]["dates_data"][date_str]["normal"] += q
        item_map[tid]["dates_data"][date_str]["total"] += q

    rows = list(item_map.values())
    rows.sort(key=lambda x: sku_sort_key(x.get("sku", ""), x.get("tube_name", "")))

    return Response({
        "data": rows,
        "count": len(rows),
        "date": date_param or str(today),
        "month": month_param or today.strftime("%Y-%m"),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_production_sheet(request):
    """
    Export Cycle Tube production sheet as styled Excel workbook (3 sheets):
      1. Daily Matrix (1-31) - Calendar grid with daily quantities
      2. Monthly Summary - Item consolidated totals with weights
      3. Date-Wise Production - Detailed daily entry ledger
    Sorted strictly by coding (SKU).
    """
    import calendar
    from io import BytesIO
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    today = datetime.date.today()
    date_param = request.query_params.get("date", "").strip()
    month_param = request.query_params.get("month", "").strip()

    is_single_date = False
    if date_param:
        try:
            parts = date_param.split("-")
            year, month = int(parts[0]), int(parts[1])
            is_single_date = True
        except (ValueError, IndexError):
            year, month = today.year, today.month
    elif month_param and month_param != "all":
        try:
            parts = month_param.split("-")
            year, month = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            year, month = today.year, today.month
    else:
        year, month = today.year, today.month

    _, num_days = calendar.monthrange(year, month)
    month_name = calendar.month_name[month].upper()
    label = f"{date_param}" if is_single_date else f"{month_name} {year}"

    # ── Aesthetic Slate & Corporate Indigo Theme ──
    C_CORP_NAVY = "0F172A"   # Slate 900 (Corporate Banner)
    C_HDR_NAVY  = "1E293B"   # Slate 800 (Headers)
    C_SUB_SLATE = "334155"   # Slate 700 (Sub-headers)
    C_DAY_HDR   = "475569"   # Slate 600 (Day sub-headers)
    C_ZEBRA     = "F8FAFC"   # Slate 50 (Alternate rows)
    C_FOOT      = "F1F5F9"   # Slate 100 (Total footer)
    C_BORDER    = "E2E8F0"   # Slate 200 (Soft borders)
    C_CODE_BG   = "F1F5F9"   # Code column light background
    C_CODE_TXT  = "1D4ED8"   # Blue 700
    C_MUTED     = "94A3B8"   # Slate 400

    f_corp = Font(name="Segoe UI", size=13, bold=True, color="FFFFFF")
    f_addr = Font(name="Segoe UI", size=9, bold=False, color=C_MUTED)
    f_title = Font(name="Segoe UI", size=10.5, bold=True, color="FFFFFF")
    f_hdr = Font(name="Segoe UI", size=9.5, bold=True, color="FFFFFF")
    f_subhdr = Font(name="Segoe UI", size=8.5, bold=True, color="FFFFFF")
    f_day = Font(name="Segoe UI", size=8, bold=True, color="FFFFFF")
    f_data = Font(name="Segoe UI", size=9.5)
    f_bold = Font(name="Segoe UI", size=9.5, bold=True)
    f_code = Font(name="Segoe UI", size=9.5, bold=True, color=C_CODE_TXT)
    f_foot = Font(name="Segoe UI", size=10, bold=True, color=C_CORP_NAVY)

    fill_corp = PatternFill("solid", fgColor=C_CORP_NAVY)
    fill_hdr  = PatternFill("solid", fgColor=C_HDR_NAVY)
    fill_sub  = PatternFill("solid", fgColor=C_SUB_SLATE)
    fill_day  = PatternFill("solid", fgColor=C_DAY_HDR)
    fill_zebra = PatternFill("solid", fgColor=C_ZEBRA)
    fill_foot = PatternFill("solid", fgColor=C_FOOT)
    fill_code = PatternFill("solid", fgColor=C_CODE_BG)

    al_center = Alignment(horizontal="center", vertical="center")
    al_left = Alignment(horizontal="left", vertical="center")
    al_right = Alignment(horizontal="right", vertical="center")

    thin_border = Border(
        left=Side(style="thin", color=C_BORDER),
        right=Side(style="thin", color=C_BORDER),
        top=Side(style="thin", color=C_BORDER),
        bottom=Side(style="thin", color=C_BORDER)
    )
    foot_border = Border(
        left=Side(style="thin", color=C_BORDER),
        right=Side(style="thin", color=C_BORDER),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="double", color=C_CORP_NAVY)
    )

    # CRITICAL FIX: ALWAYS query FULL MONTH entries for Sheet 1 & 2
    month_entries = list(CycleTubeEntry.objects.filter(
        entry_type='production', date__year=year, date__month=month
    ).exclude(bucket="rfm_stock").select_related('tube_item', 'user'))

    prod_data = {}
    for e in month_entries:
        tid = e.tube_item_id
        day = e.date.day
        prod_data[(tid, day)] = prod_data.get((tid, day), 0) + (e.quantity or 0)

    all_items = sorted(
        CycleTubeItem.objects.filter(is_active=True),
        key=lambda x: sku_sort_key(x.sku, x.size)
    )

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ══════════════════════════════════════════════════════════════
    # SHEET 1: Daily Matrix (1-31)
    # ══════════════════════════════════════════════════════════════
    ws1 = wb.create_sheet("Daily Matrix (1-31)")
    ws1.views.sheetView[0].showGridLines = True

    tot_start_col = 7 + num_days
    last_col = tot_start_col + 2

    # Title Banner (Clean, unified dark header)
    ws1.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    c1 = ws1.cell(1, 1, "RADHU INDUSTRIES")
    c1.font = f_corp; c1.fill = fill_corp; c1.alignment = al_center
    ws1.row_dimensions[1].height = 28

    ws1.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
    c2 = ws1.cell(2, 1, "17/5 Mile Stone, Delhi-Meerut Road, Murad Nagar, U.P. - 201206")
    c2.font = f_addr; c2.fill = fill_corp; c2.alignment = al_center
    ws1.row_dimensions[2].height = 18

    ws1.merge_cells(start_row=3, start_column=1, end_row=3, end_column=last_col)
    c3 = ws1.cell(3, 1, f"CYCLE TUBE — DATE-WISE PRODUCTION MATRIX  |  {label}")
    c3.font = f_title; c3.fill = fill_hdr; c3.alignment = al_center
    ws1.row_dimensions[3].height = 24

    ws1.row_dimensions[4].height = 6  # Aesthetic spacer row

    # Row 5: Group Headers
    ws1.merge_cells("A5:F5")
    h_spec = ws1.cell(5, 1, "ITEM SPECIFICATIONS")
    h_spec.font = f_hdr; h_spec.fill = fill_hdr; h_spec.alignment = al_center
    for c in range(1, 7):
        ws1.cell(5, c).border = thin_border; ws1.cell(5, c).fill = fill_hdr

    for d in range(1, num_days + 1):
        col = 6 + d
        c = ws1.cell(5, col, f"{d:02d}-{month_name[:3]}")
        c.font = f_subhdr; c.fill = fill_sub; c.alignment = al_center; c.border = thin_border

    ws1.merge_cells(start_row=5, start_column=tot_start_col, end_row=5, end_column=last_col)
    h_tot = ws1.cell(5, tot_start_col, "MONTHLY TOTALS")
    h_tot.font = f_hdr; h_tot.fill = fill_hdr; h_tot.alignment = al_center
    for c in range(tot_start_col, last_col + 1):
        ws1.cell(5, c).border = thin_border; ws1.cell(5, c).fill = fill_hdr
    ws1.row_dimensions[5].height = 22

    # Row 6: Sub-headers
    ws1.row_dimensions[6].height = 20
    fixed_hdrs = ["#", "CODE", "TUBE ITEM", "SIZE", "TYPE", "BRAND"]
    for ci, h in enumerate(fixed_hdrs, 1):
        c = ws1.cell(6, ci, h)
        c.font = f_hdr; c.fill = fill_hdr; c.alignment = al_center; c.border = thin_border

    for d in range(1, num_days + 1):
        col = 6 + d
        c = ws1.cell(6, col, f"D{d}")
        c.font = f_day; c.fill = fill_day; c.alignment = al_center; c.border = thin_border

    for idx, h_tot in enumerate(["TOTAL PCS", "WT/PC (KG)", "TOTAL KGS"]):
        col = tot_start_col + idx
        c = ws1.cell(6, col, h_tot)
        c.font = f_hdr; c.fill = fill_hdr; c.alignment = al_center; c.border = thin_border

    # Fill Rows (Row 7+)
    r_idx = 7
    for idx, item in enumerate(all_items, 1):
        rf = fill_zebra if idx % 2 == 0 else PatternFill("solid", fgColor="FFFFFF")
        ws1.row_dimensions[r_idx].height = 19

        c_sno = ws1.cell(r_idx, 1, idx)
        c_sno.alignment = al_center; c_sno.font = f_data; c_sno.fill = rf; c_sno.border = thin_border

        c_code = ws1.cell(r_idx, 2, item.sku or "")
        c_code.alignment = al_center; c_code.font = f_code; c_code.fill = fill_code; c_code.border = thin_border

        c_name = ws1.cell(r_idx, 3, f"{item.size or ''} {item.type or ''} {item.brand or ''}".strip())
        c_name.alignment = al_left; c_name.font = f_bold; c_name.fill = rf; c_name.border = thin_border

        c_size = ws1.cell(r_idx, 4, item.size or "")
        c_size.alignment = al_center; c_size.font = f_data; c_size.fill = rf; c_size.border = thin_border

        c_type = ws1.cell(r_idx, 5, item.type or "")
        c_type.alignment = al_center; c_type.font = f_data; c_type.fill = rf; c_type.border = thin_border

        c_brand = ws1.cell(r_idx, 6, item.brand or "")
        c_brand.alignment = al_left; c_brand.font = f_data; c_brand.fill = rf; c_brand.border = thin_border

        for d in range(1, num_days + 1):
            col = 6 + d
            val = prod_data.get((item.id, d), 0)
            c_q = ws1.cell(r_idx, col, val if val > 0 else None)
            c_q.alignment = al_right; c_q.border = thin_border; c_q.fill = rf
            if val > 0:
                c_q.font = Font(name="Segoe UI", size=9.5, bold=True, color="1D4ED8")

        f_first = get_column_letter(7)
        f_last = get_column_letter(6 + num_days)
        tot_pcs = ws1.cell(r_idx, tot_start_col, f'=IF(SUM({f_first}{r_idx}:{f_last}{r_idx})=0,"",SUM({f_first}{r_idx}:{f_last}{r_idx}))')
        tot_pcs.font = f_bold; tot_pcs.alignment = al_right; tot_pcs.border = thin_border; tot_pcs.fill = fill_zebra

        w_val = float(item.weight or 0.950)
        c_wt = ws1.cell(r_idx, tot_start_col + 1, w_val)
        c_wt.font = f_data; c_wt.alignment = al_right; c_wt.border = thin_border; c_wt.fill = fill_zebra

        col_pcs_let = get_column_letter(tot_start_col)
        col_wt_let = get_column_letter(tot_start_col + 1)
        tot_kgs = ws1.cell(r_idx, tot_start_col + 2, f'=IF(OR({col_pcs_let}{r_idx}="",{col_pcs_let}{r_idx}=0),"",ROUND({col_pcs_let}{r_idx}*{col_wt_let}{r_idx},2))')
        tot_kgs.font = f_bold; tot_kgs.alignment = al_right; tot_kgs.border = thin_border; tot_kgs.fill = fill_zebra

        r_idx += 1

    # Footer
    foot_row = r_idx
    ws1.row_dimensions[foot_row].height = 24
    ws1.merge_cells(f"A{foot_row}:F{foot_row}")
    f_lbl = ws1.cell(foot_row, 1, "TOTAL PRODUCTION")
    f_lbl.font = f_foot; f_lbl.alignment = al_center; f_lbl.fill = fill_foot
    for c in range(1, 7):
        ws1.cell(foot_row, c).border = foot_border; ws1.cell(foot_row, c).fill = fill_foot

    for col in range(7, tot_start_col + 1):
        col_let = get_column_letter(col)
        c = ws1.cell(foot_row, col, f"=SUM({col_let}7:{col_let}{foot_row - 1})")
        c.font = f_foot; c.alignment = al_right; c.border = foot_border; c.fill = fill_foot

    col_wt_l = get_column_letter(tot_start_col + 1)
    c_wt_blank = ws1.cell(foot_row, tot_start_col + 1, "")
    c_wt_blank.border = foot_border; c_wt_blank.fill = fill_foot

    col_kgs_let = get_column_letter(last_col)
    c_tot_kg = ws1.cell(foot_row, last_col, f"=SUM({col_kgs_let}7:{col_kgs_let}{foot_row - 1})")
    c_tot_kg.font = f_foot; c_tot_kg.alignment = al_right; c_tot_kg.border = foot_border; c_tot_kg.fill = fill_foot

    ws1.column_dimensions["A"].width = 5
    ws1.column_dimensions["B"].width = 10
    ws1.column_dimensions["C"].width = 24
    ws1.column_dimensions["D"].width = 12
    ws1.column_dimensions["E"].width = 10
    ws1.column_dimensions["F"].width = 15
    for d in range(1, num_days + 1):
        ws1.column_dimensions[get_column_letter(6 + d)].width = 6.5
    ws1.column_dimensions[get_column_letter(tot_start_col)].width = 13
    ws1.column_dimensions[get_column_letter(tot_start_col + 1)].width = 12
    ws1.column_dimensions[get_column_letter(tot_start_col + 2)].width = 14

    # ══════════════════════════════════════════════════════════════
    # SHEET 2: Monthly Summary
    # ══════════════════════════════════════════════════════════════
    ws2 = wb.create_sheet("Monthly Summary")
    ws2.views.sheetView[0].showGridLines = True

    ws2.merge_cells("A1:I1")
    c1 = ws2.cell(1, 1, "RADHU INDUSTRIES")
    c1.font = f_corp; c1.fill = fill_corp; c1.alignment = al_center
    ws2.row_dimensions[1].height = 28

    ws2.merge_cells("A2:I2")
    c2 = ws2.cell(2, 1, "17/5 Mile Stone, Delhi-Meerut Road, Murad Nagar, U.P. - 201206")
    c2.font = f_addr; c2.fill = fill_corp; c2.alignment = al_center
    ws2.row_dimensions[2].height = 18

    ws2.merge_cells("A3:I3")
    c3 = ws2.cell(3, 1, f"CYCLE TUBE — MONTHLY PRODUCTION SUMMARY  |  {label}")
    c3.font = f_title; c3.fill = fill_hdr; c3.alignment = al_center
    ws2.row_dimensions[3].height = 24

    ws2.row_dimensions[4].height = 6

    sum_hdrs = ["#", "CODE", "TUBE ITEM", "SIZE", "TYPE", "BRAND", "MONTH TOTAL (PCS)", "WT/PC (KG)", "TOTAL KGS"]
    ws2.row_dimensions[5].height = 24
    for ci, h in enumerate(sum_hdrs, 1):
        c = ws2.cell(5, ci, h)
        c.font = f_hdr; c.fill = fill_hdr; c.alignment = al_center; c.border = thin_border

    r2_idx = 6
    for idx, item in enumerate(all_items, 1):
        rf = fill_zebra if idx % 2 == 0 else PatternFill("solid", fgColor="FFFFFF")
        ws2.row_dimensions[r2_idx].height = 19

        tot_q = sum(prod_data.get((item.id, d), 0) for d in range(1, num_days + 1))
        w_val = float(item.weight or 0.950)

        ws2.cell(r2_idx, 1, idx).alignment = al_center
        ws2.cell(r2_idx, 2, item.sku or "").alignment = al_center
        ws2.cell(r2_idx, 3, f"{item.size or ''} {item.type or ''} {item.brand or ''}".strip()).alignment = al_left
        ws2.cell(r2_idx, 4, item.size or "").alignment = al_center
        ws2.cell(r2_idx, 5, item.type or "").alignment = al_center
        ws2.cell(r2_idx, 6, item.brand or "").alignment = al_left
        
        ws2.cell(r2_idx, 7, tot_q if tot_q > 0 else None).alignment = al_right
        ws2.cell(r2_idx, 8, w_val).alignment = al_right
        ws2.cell(r2_idx, 9, f'=IF(OR(G{r2_idx}="",G{r2_idx}=0),"",ROUND(G{r2_idx}*H{r2_idx},2))').alignment = al_right

        for c in range(1, 10):
            cell = ws2.cell(r2_idx, c)
            cell.border = thin_border
            cell.fill = fill_code if c == 2 else rf
            cell.font = f_code if c == 2 else (f_bold if c in [3, 7, 9] else f_data)

        r2_idx += 1

    # Footer
    ws2.merge_cells(f"A{r2_idx}:F{r2_idx}")
    t2_lbl = ws2.cell(r2_idx, 1, "TOTALS")
    t2_lbl.font = f_foot; t2_lbl.alignment = al_center; t2_lbl.fill = fill_foot
    for c in range(1, 7):
        ws2.cell(r2_idx, c).border = foot_border; ws2.cell(r2_idx, c).fill = fill_foot

    c_tot_pcs = ws2.cell(r2_idx, 7, f"=SUM(G6:G{r2_idx - 1})")
    c_tot_pcs.font = f_foot; c_tot_pcs.alignment = al_right; c_tot_pcs.border = foot_border; c_tot_pcs.fill = fill_foot

    c_w_blank = ws2.cell(r2_idx, 8, "")
    c_w_blank.border = foot_border; c_w_blank.fill = fill_foot

    c_tot_kgs = ws2.cell(r2_idx, 9, f"=SUM(I6:I{r2_idx - 1})")
    c_tot_kgs.font = f_foot; c_tot_kgs.alignment = al_right; c_tot_kgs.border = foot_border; c_tot_kgs.fill = fill_foot

    ws2.column_dimensions["A"].width = 5
    ws2.column_dimensions["B"].width = 10
    ws2.column_dimensions["C"].width = 26
    ws2.column_dimensions["D"].width = 13
    ws2.column_dimensions["E"].width = 11
    ws2.column_dimensions["F"].width = 16
    ws2.column_dimensions["G"].width = 18
    ws2.column_dimensions["H"].width = 13
    ws2.column_dimensions["I"].width = 16

    # ══════════════════════════════════════════════════════════════
    # SHEET 3: Date-Wise Production
    # ══════════════════════════════════════════════════════════════
    ws3 = wb.create_sheet("Date-Wise Production")
    ws3.views.sheetView[0].showGridLines = True

    ws3.merge_cells("A1:J1")
    c1 = ws3.cell(1, 1, "RADHU INDUSTRIES")
    c1.font = f_corp; c1.fill = fill_corp; c1.alignment = al_center
    ws3.row_dimensions[1].height = 28

    ws3.merge_cells("A2:J2")
    c2 = ws3.cell(2, 1, "17/5 Mile Stone, Delhi-Meerut Road, Murad Nagar, U.P. - 201206")
    c2.font = f_addr; c2.fill = fill_corp; c2.alignment = al_center
    ws3.row_dimensions[2].height = 18

    ws3.merge_cells("A3:J3")
    c3 = ws3.cell(3, 1, f"CYCLE TUBE — DAILY PRODUCTION LOG  |  {label}")
    c3.font = f_title; c3.fill = fill_hdr; c3.alignment = al_center
    ws3.row_dimensions[3].height = 24

    ws3.row_dimensions[4].height = 6

    led_hdrs = ["Date", "CODE", "Tube Item", "Size", "Type", "Brand", "Quality", "Quantity", "Weight (Kg)", "Total Kgs"]
    ws3.row_dimensions[5].height = 24
    for ci, h in enumerate(led_hdrs, 1):
        c = ws3.cell(5, ci, h)
        c.font = f_hdr; c.fill = fill_hdr; c.alignment = al_center; c.border = thin_border

    # If single date, filter or show all month
    if is_single_date:
        filtered_entries = [e for e in month_entries if str(e.date) == date_param]
        ledger_entries = filtered_entries if filtered_entries else month_entries
    else:
        ledger_entries = month_entries

    sorted_entries = sorted(ledger_entries, key=lambda e: (e.date, sku_sort_key(e.tube_item.sku if e.tube_item else "", e.tube_item.size if e.tube_item else "")))
    r3_idx = 6
    for idx, e in enumerate(sorted_entries, 1):
        rf = fill_zebra if idx % 2 == 0 else PatternFill("solid", fgColor="FFFFFF")
        ws3.row_dimensions[r3_idx].height = 19
        item = e.tube_item
        w_val = float(item.weight or 0.950) if item else 0.950
        qty = e.quantity or 0

        ws3.cell(r3_idx, 1, e.date.strftime("%d-%m-%Y")).alignment = al_center
        ws3.cell(r3_idx, 2, item.sku if item else "").alignment = al_center
        ws3.cell(r3_idx, 3, f"{item.size or ''} {item.type or ''} {item.brand or ''}".strip() if item else "").alignment = al_left
        ws3.cell(r3_idx, 4, item.size if item else "").alignment = al_center
        ws3.cell(r3_idx, 5, item.type if item else "").alignment = al_center
        ws3.cell(r3_idx, 6, item.brand if item else "").alignment = al_left
        ws3.cell(r3_idx, 7, e.tube_quality or "normal").alignment = al_center
        ws3.cell(r3_idx, 8, qty).alignment = al_right
        ws3.cell(r3_idx, 9, w_val).alignment = al_right
        ws3.cell(r3_idx, 10, f'=IF(OR(H{r3_idx}="",H{r3_idx}=0),"",ROUND(H{r3_idx}*I{r3_idx},2))').alignment = al_right

        for c in range(1, 11):
            cell = ws3.cell(r3_idx, c)
            cell.border = thin_border
            cell.fill = fill_code if c == 2 else rf
            cell.font = f_code if c == 2 else (f_bold if c in [8, 10] else f_data)

        r3_idx += 1

    if sorted_entries:
        ws3.merge_cells(f"A{r3_idx}:G{r3_idx}")
        t3_lbl = ws3.cell(r3_idx, 1, "TOTAL")
        t3_lbl.font = f_foot; t3_lbl.alignment = al_center; t3_lbl.fill = fill_foot
        for c in range(1, 8):
            ws3.cell(r3_idx, c).border = foot_border; ws3.cell(r3_idx, c).fill = fill_foot
        
        c_q_tot = ws3.cell(r3_idx, 8, f"=SUM(H6:H{r3_idx - 1})")
        c_q_tot.font = f_foot; c_q_tot.alignment = al_right; c_q_tot.border = foot_border; c_q_tot.fill = fill_foot

        c_w_bl = ws3.cell(r3_idx, 9, "")
        c_w_bl.border = foot_border; c_w_bl.fill = fill_foot

        c_kg_tot = ws3.cell(r3_idx, 10, f"=SUM(J6:J{r3_idx - 1})")
        c_kg_tot.font = f_foot; c_kg_tot.alignment = al_right; c_kg_tot.border = foot_border; c_kg_tot.fill = fill_foot

    ws3.column_dimensions["A"].width = 12
    ws3.column_dimensions["B"].width = 10
    ws3.column_dimensions["C"].width = 26
    ws3.column_dimensions["D"].width = 13
    ws3.column_dimensions["E"].width = 11
    ws3.column_dimensions["F"].width = 16
    ws3.column_dimensions["G"].width = 12
    ws3.column_dimensions["H"].width = 14
    ws3.column_dimensions["I"].width = 13
    ws3.column_dimensions["J"].width = 16

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"CYCLE_TUBE_PRODUCTION_{year}_{month:02d}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transactions_ledger(request):
    """
    Bank Passbook / Stock Ledger statement for Cycle Tube items.
    Calculates Opening Balance, Inflows (Production), Outflows (Sale),
    Adjustments, and Running Balance.
    """
    today = datetime.date.today()
    item_id_param = request.query_params.get("tube_item") or request.query_params.get("item_id")
    bucket_param = request.query_params.get("bucket", "stock").strip()
    from_date_str = request.query_params.get("from_date") or request.query_params.get("start_date")
    to_date_str = request.query_params.get("to_date") or request.query_params.get("end_date")
    search_q = request.query_params.get("search", "").strip().lower()

    try:
        from_date = datetime.datetime.strptime(from_date_str, "%Y-%m-%d").date() if from_date_str else today.replace(day=1)
    except:
        from_date = today.replace(day=1)

    try:
        to_date = datetime.datetime.strptime(to_date_str, "%Y-%m-%d").date() if to_date_str else today
    except:
        to_date = today

    all_items = CycleTubeItem.objects.filter(is_active=True).order_by("size", "brand")
    items_list = [
        {
            "id": it.id,
            "name": str(it),
            "size": it.size,
            "type": it.type,
            "brand": it.brand,
            "stock": it.stock,
            "rfm_stock": it.rfm_stock,
            "total_stock": it.total_stock,
        }
        for it in all_items
    ]

    selected_item = None
    selected_item_obj = None
    if item_id_param and item_id_param != "all":
        try:
            selected_item_obj = CycleTubeItem.objects.get(pk=int(item_id_param))
            selected_item = {
                "id": selected_item_obj.id,
                "name": str(selected_item_obj),
                "size": selected_item_obj.size,
                "type": selected_item_obj.type,
                "brand": selected_item_obj.brand,
                "stock": selected_item_obj.stock,
                "rfm_stock": selected_item_obj.rfm_stock,
                "total_stock": selected_item_obj.total_stock,
            }
        except (CycleTubeItem.DoesNotExist, ValueError):
            selected_item_obj = None
    elif item_id_param != "all":
        from django.db.models import Count
        most_active = CycleTubeEntry.objects.values("tube_item").annotate(c=Count("id")).order_by("-c").first()
        if most_active:
            try:
                selected_item_obj = CycleTubeItem.objects.get(pk=most_active["tube_item"])
            except:
                selected_item_obj = all_items.first()
        else:
            selected_item_obj = all_items.first()

        if selected_item_obj:
            selected_item = {
                "id": selected_item_obj.id,
                "name": str(selected_item_obj),
                "size": selected_item_obj.size,
                "type": selected_item_obj.type,
                "brand": selected_item_obj.brand,
                "stock": selected_item_obj.stock,
                "rfm_stock": selected_item_obj.rfm_stock,
                "total_stock": selected_item_obj.total_stock,
            }

    def extract_party(remark_text):
        if not remark_text:
            return ""
        if "Party:" in remark_text:
            part = remark_text.split("Party:")[1].strip()
            if "[" in part and "]" in part:
                part = part.split("[")[0].strip()
            return part
        return ""

    prior_qs = CycleTubeEntry.objects.filter(date__lt=from_date)
    period_qs = CycleTubeEntry.objects.filter(date__gte=from_date, date__lte=to_date)

    if selected_item_obj:
        prior_qs = prior_qs.filter(tube_item=selected_item_obj)
        period_qs = period_qs.filter(tube_item=selected_item_obj)

    if bucket_param and bucket_param != "all":
        prior_qs = prior_qs.filter(bucket=bucket_param)
        period_qs = period_qs.filter(bucket=bucket_param)

    opening_balance = 0
    for e in prior_qs.order_by("date", "id"):
        if e.entry_type == "production":
            opening_balance += e.quantity
        elif e.entry_type == "sale":
            opening_balance -= e.quantity
        elif e.entry_type == "adjustment":
            opening_balance += e.quantity

    running_balance = opening_balance
    transactions = []
    total_in = 0
    total_out = 0

    period_entries = list(period_qs.select_related("tube_item").order_by("date", "created_at", "id"))

    for e in period_entries:
        in_qty = 0
        out_qty = 0
        narration = ""
        party_name = extract_party(e.remark)

        if e.entry_type == "production":
            in_qty = e.quantity
            out_qty = 0
            narration = f"Daily Production ({e.get_tube_quality_display() if hasattr(e, 'get_tube_quality_display') else e.tube_quality})"
            if e.remark:
                narration += f" — {e.remark}"
        elif e.entry_type == "sale":
            in_qty = 0
            out_qty = e.quantity
            narration = "Sale / Dispatch"
            if party_name:
                narration = f"Dispatched: {party_name}"
            if e.bill_number:
                narration += f" (Bill: {e.bill_number})"
            if e.remark and not party_name:
                narration += f" — {e.remark}"
        elif e.entry_type == "adjustment":
            if e.quantity >= 0:
                in_qty = e.quantity
                out_qty = 0
                narration = f"Stock Adjustment (+) {e.remark or ''}".strip()
            else:
                in_qty = 0
                out_qty = abs(e.quantity)
                narration = f"Stock Adjustment (-) {e.remark or ''}".strip()

        running_balance += (in_qty - out_qty)
        total_in += in_qty
        total_out += out_qty

        row_searchable = f"{e.date} {e.bill_number} {party_name} {e.remark} {narration} {str(e.tube_item)}".lower()
        if search_q and search_q not in row_searchable:
            continue

        transactions.append({
            "id": e.id,
            "date": str(e.date),
            "created_at": e.created_at.strftime("%I:%M %p") if e.created_at else "",
            "entry_type": e.entry_type,
            "bucket": e.bucket,
            "bucket_display": e.get_bucket_display(),
            "tube_item_id": e.tube_item_id,
            "tube_name": str(e.tube_item),
            "bill_number": e.bill_number or "-",
            "party_name": party_name or "-",
            "narration": narration,
            "remark": e.remark or "",
            "in_qty": in_qty,
            "out_qty": out_qty,
            "balance": running_balance,
        })

    return Response({
        "items": items_list,
        "selected_item": selected_item,
        "bucket": bucket_param,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "opening_balance": opening_balance,
        "closing_balance": running_balance,
        "total_in": total_in,
        "total_out": total_out,
        "net_change": total_in - total_out,
        "total_count": len(transactions),
        "transactions": transactions,
    })


@api_view(["POST", "PATCH"])
@permission_classes([IsAuthenticated])
def update_tube_sku(request):
    """Update SKU number for a CycleTubeItem."""
    item_id = request.data.get("id") or request.data.get("item_id")
    sku = (request.data.get("sku") or "").strip()
    if not item_id:
        return Response({"error": "Item ID is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        item = CycleTubeItem.objects.get(id=item_id)
        item.sku = sku
        item.save(update_fields=["sku"])
        return Response({
            "status": "success",
            "id": item.id,
            "sku": item.sku,
            "message": "SKU updated successfully."
        })
    except CycleTubeItem.DoesNotExist:
        return Response({"error": "Cycle tube item not found."}, status=status.HTTP_404_NOT_FOUND)
