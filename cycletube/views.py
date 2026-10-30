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
                "tube_name": f"{e.tube_item.size} {e.tube_item.type} {e.tube_item.brand}".strip(),
                "size": e.tube_item.size,
                "type": e.tube_item.type,
                "brand": e.tube_item.brand,
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
    rows.sort(key=lambda x: (x["size"], x["type"], x["brand"]))

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
    Export Cycle Tube production sheet as styled Excel workbook (3 sheets).
    ?month=YYYY-MM  OR  ?date=YYYY-MM-DD
    """
    import calendar
    from io import BytesIO
    import openpyxl
    from openpyxl.styles import (
        Font, PatternFill, Alignment, Border, Side, GradientFill
    )
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse

    today = datetime.date.today()
    date_param = request.query_params.get("date")
    month_param = request.query_params.get("month")

    if date_param:
        try:
            target_date = datetime.datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            target_date = today
        year, month_num = target_date.year, target_date.month
        entries = CycleTubeEntry.objects.filter(
            entry_type="production", date=target_date
        ).exclude(bucket="rfm_stock").select_related("tube_item")
        label = target_date.strftime("%d-%b-%Y")
    elif month_param:
        try:
            parts = month_param.split("-")
            year, month_num = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            year, month_num = today.year, today.month
        entries = CycleTubeEntry.objects.filter(
            entry_type="production", date__year=year, date__month=month_num
        ).exclude(bucket="rfm_stock").select_related("tube_item")
        label = datetime.date(year, month_num, 1).strftime("%B %Y")
    else:
        year, month_num = today.year, today.month
        entries = CycleTubeEntry.objects.filter(
            entry_type="production", date__year=year, date__month=month_num
        ).exclude(bucket="rfm_stock").select_related("tube_item")
        label = today.strftime("%B %Y")

    days_in_month = calendar.monthrange(year, month_num)[1]

    # Build item_map: {tid: {info, days: {1..31: total_qty}, total, weight}}
    item_map = {}
    for e in entries:
        tid = e.tube_item.id
        if tid not in item_map:
            item_map[tid] = {
                "sno": 0,
                "tube_name": f"{e.tube_item.size} {e.tube_item.type} {e.tube_item.brand}".strip(),
                "size": e.tube_item.size or "",
                "type": e.tube_item.type or "",
                "brand": e.tube_item.brand or "",
                "weight": float(e.tube_item.weight or 0),
                "days": {},
                "total": 0,
            }
        day_num = e.date.day
        item_map[tid]["days"][day_num] = item_map[tid]["days"].get(day_num, 0) + (e.quantity or 0)
        item_map[tid]["total"] += (e.quantity or 0)

    rows = sorted(item_map.values(), key=lambda x: (x["size"], x["type"], x["brand"]))
    for i, r in enumerate(rows):
        r["sno"] = i + 1
        r["total_kgs"] = round(r["total"] * r["weight"], 2)

    # ── Styles ──────────────────────────────────────────────────────────────
    def thin_border():
        s = Side(style="thin", color="BFBFBF")
        return Border(left=s, right=s, top=s, bottom=s)

    def hdr_font(bold=True, size=10, color="FFFFFF"):
        return Font(name="Calibri", bold=bold, size=size, color=color)

    def cell_font(bold=False, size=10, color="000000"):
        return Font(name="Calibri", bold=bold, size=size, color=color)

    def fill(hex_color):
        return PatternFill("solid", fgColor=hex_color)

    CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
    LEFT   = Alignment(horizontal="left",   vertical="center", wrap_text=True)
    RIGHT  = Alignment(horizontal="right",  vertical="center")

    HDR_FILL   = fill("1E3A5F")   # dark navy
    SUB_FILL   = fill("2D6A9F")   # mid blue
    ALT1_FILL  = fill("EBF4FB")   # light blue stripe
    ALT2_FILL  = fill("FFFFFF")
    FOOT_FILL  = fill("1E3A5F")
    DAY_FILL   = fill("154360")   # day-matrix header
    ZERO_COLOR = "BFBFBF"

    wb = openpyxl.Workbook()

    # ════════════════════════════════════════════════════════════════════════
    # SHEET 1 — Date-Wise Production Ledger
    # ════════════════════════════════════════════════════════════════════════
    ws1 = wb.active
    ws1.title = "Date-Wise Production"
    ws1.sheet_view.showGridLines = False

    # Title
    ws1.merge_cells("A1:H1")
    t = ws1["A1"]
    t.value = f"CYCLE TUBE — DATE-WISE PRODUCTION  |  {label}"
    t.font = Font(name="Calibri", bold=True, size=14, color="FFFFFF")
    t.fill = HDR_FILL
    t.alignment = CENTER
    ws1.row_dimensions[1].height = 30

    # Sub-title row
    ws1.merge_cells("A2:H2")
    s2 = ws1["A2"]
    s2.value = "Radhu Rubber Industries"
    s2.font = Font(name="Calibri", bold=False, size=10, color="FFFFFF")
    s2.fill = SUB_FILL
    s2.alignment = CENTER
    ws1.row_dimensions[2].height = 18

    # Column headers
    col_hdrs = ["S.No", "Tube Name", "Size", "Type", "Brand", "Total Production", "Weight (Kg)", "Total Kgs"]
    ws1.row_dimensions[3].height = 22
    for ci, h in enumerate(col_hdrs, 1):
        c = ws1.cell(row=3, column=ci, value=h)
        c.font = hdr_font()
        c.fill = HDR_FILL
        c.alignment = CENTER
        c.border = thin_border()

    col_widths1 = [6, 30, 12, 12, 18, 18, 12, 12]
    for ci, w in enumerate(col_widths1, 1):
        ws1.column_dimensions[get_column_letter(ci)].width = w

    grand_total = 0
    grand_kgs   = 0.0
    for ri, row in enumerate(rows):
        excel_row = ri + 4
        row_fill = ALT1_FILL if ri % 2 == 0 else fill("FFFFFF")
        vals = [
            row["sno"],
            row["tube_name"],
            row["size"],
            row["type"],
            row["brand"],
            row["total"],
            row["weight"],
            row["total_kgs"],
        ]
        aligns = [CENTER, LEFT, CENTER, CENTER, CENTER, CENTER, CENTER, CENTER]
        for ci, (v, al) in enumerate(zip(vals, aligns), 1):
            c = ws1.cell(row=excel_row, column=ci, value=v)
            c.font = cell_font(bold=(ci == 6))
            c.fill = row_fill
            c.alignment = al
            c.border = thin_border()
            if ci == 6:
                c.font = Font(name="Calibri", bold=True, size=10, color="1A5276")
        grand_total += row["total"]
        grand_kgs   += row["total_kgs"]

    # Footer
    foot_row = len(rows) + 4
    ws1.row_dimensions[foot_row].height = 20
    for ci in range(1, 9):
        c = ws1.cell(row=foot_row, column=ci)
        c.fill = FOOT_FILL
        c.border = thin_border()
    ws1.cell(row=foot_row, column=1, value="TOTAL").font = hdr_font()
    ws1.cell(row=foot_row, column=1).alignment = CENTER
    ws1.cell(row=foot_row, column=6, value=grand_total).font = hdr_font()
    ws1.cell(row=foot_row, column=6).alignment = CENTER
    ws1.cell(row=foot_row, column=8, value=round(grand_kgs, 2)).font = hdr_font()
    ws1.cell(row=foot_row, column=8).alignment = CENTER

    # ════════════════════════════════════════════════════════════════════════
    # SHEET 2 — Monthly Summary (same as sheet 1 but with per-item weight kg totals)
    # ════════════════════════════════════════════════════════════════════════
    ws2 = wb.create_sheet("Monthly Summary")
    ws2.sheet_view.showGridLines = False

    ws2.merge_cells("A1:H1")
    t2 = ws2["A1"]
    t2.value = f"CYCLE TUBE — MONTHLY SUMMARY  |  {label}"
    t2.font = Font(name="Calibri", bold=True, size=14, color="FFFFFF")
    t2.fill = HDR_FILL
    t2.alignment = CENTER
    ws2.row_dimensions[1].height = 30

    ws2.merge_cells("A2:H2")
    s22 = ws2["A2"]
    s22.value = "Radhu Rubber Industries"
    s22.font = Font(name="Calibri", bold=False, size=10, color="FFFFFF")
    s22.fill = SUB_FILL
    s22.alignment = CENTER
    ws2.row_dimensions[2].height = 18

    sum_hdrs = ["S.No", "Tube Name", "Size", "Type", "Brand", "Month Total", "Wt/Pc (Kg)", "Total Kgs"]
    ws2.row_dimensions[3].height = 22
    for ci, h in enumerate(sum_hdrs, 1):
        c = ws2.cell(row=3, column=ci, value=h)
        c.font = hdr_font()
        c.fill = HDR_FILL
        c.alignment = CENTER
        c.border = thin_border()

    for ci, w in enumerate([6, 30, 12, 12, 18, 14, 12, 12], 1):
        ws2.column_dimensions[get_column_letter(ci)].width = w

    g2_total = 0; g2_kgs = 0.0
    for ri, row in enumerate(rows):
        er = ri + 4
        rf = ALT1_FILL if ri % 2 == 0 else fill("FFFFFF")
        vs = [row["sno"], row["tube_name"], row["size"], row["type"], row["brand"],
              row["total"], row["weight"], row["total_kgs"]]
        als = [CENTER, LEFT, CENTER, CENTER, CENTER, CENTER, CENTER, CENTER]
        for ci, (v, al) in enumerate(zip(vs, als), 1):
            c = ws2.cell(row=er, column=ci, value=v)
            c.font = cell_font(bold=(ci == 6))
            c.fill = rf; c.alignment = al; c.border = thin_border()
        g2_total += row["total"]; g2_kgs += row["total_kgs"]

    fr2 = len(rows) + 4
    for ci in range(1, 9):
        c = ws2.cell(row=fr2, column=ci)
        c.fill = FOOT_FILL; c.border = thin_border()
    ws2.cell(row=fr2, column=1, value="TOTAL").font = hdr_font()
    ws2.cell(row=fr2, column=1).alignment = CENTER
    ws2.cell(row=fr2, column=6, value=g2_total).font = hdr_font()
    ws2.cell(row=fr2, column=6).alignment = CENTER
    ws2.cell(row=fr2, column=8, value=round(g2_kgs, 2)).font = hdr_font()
    ws2.cell(row=fr2, column=8).alignment = CENTER

    # ════════════════════════════════════════════════════════════════════════
    # SHEET 3 — Daily Matrix (1-31)
    # ════════════════════════════════════════════════════════════════════════
    ws3 = wb.create_sheet("Daily Matrix (1-31)")
    ws3.sheet_view.showGridLines = False

    total_cols = 5 + days_in_month + 2   # sno+name+size+type+brand + days + total+kgs

    # Title
    ws3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    t3 = ws3.cell(row=1, column=1, value=f"CYCLE TUBE — DAILY MATRIX  |  {label}")
    t3.font = Font(name="Calibri", bold=True, size=14, color="FFFFFF")
    t3.fill = HDR_FILL; t3.alignment = CENTER
    ws3.row_dimensions[1].height = 30

    ws3.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_cols)
    s32 = ws3.cell(row=2, column=1, value="Radhu Rubber Industries")
    s32.font = Font(name="Calibri", bold=False, size=10, color="FFFFFF")
    s32.fill = SUB_FILL; s32.alignment = CENTER
    ws3.row_dimensions[2].height = 18

    # Header row
    ws3.row_dimensions[3].height = 22
    fixed_hdrs = ["S.No", "Tube Name", "Size", "Type", "Brand"]
    for ci, h in enumerate(fixed_hdrs, 1):
        c = ws3.cell(row=3, column=ci, value=h)
        c.font = hdr_font(); c.fill = HDR_FILL; c.alignment = CENTER; c.border = thin_border()

    # Day columns
    for d in range(1, days_in_month + 1):
        ci = d + 5
        c = ws3.cell(row=3, column=ci, value=d)
        c.font = hdr_font(size=9); c.fill = fill("154360"); c.alignment = CENTER; c.border = thin_border()

    for ci, h in enumerate(["TOTAL", "Total Kgs"], 1):
        col = 5 + days_in_month + ci
        c = ws3.cell(row=3, column=col, value=h)
        c.font = hdr_font(); c.fill = HDR_FILL; c.alignment = CENTER; c.border = thin_border()

    # Column widths
    ws3.column_dimensions["A"].width = 5
    ws3.column_dimensions["B"].width = 28
    for col_letter in ["C", "D", "E"]:
        ws3.column_dimensions[col_letter].width = 11
    for d in range(1, days_in_month + 1):
        ws3.column_dimensions[get_column_letter(d + 5)].width = 6
    ws3.column_dimensions[get_column_letter(5 + days_in_month + 1)].width = 8
    ws3.column_dimensions[get_column_letter(5 + days_in_month + 2)].width = 10

    # Day column totals accumulator
    day_col_totals = {d: 0 for d in range(1, days_in_month + 1)}
    grand_tot3 = 0; grand_kgs3 = 0.0

    for ri, row in enumerate(rows):
        er = ri + 4
        rf = ALT1_FILL if ri % 2 == 0 else fill("FFFFFF")

        fixed_vals = [row["sno"], row["tube_name"], row["size"], row["type"], row["brand"]]
        fixed_als  = [CENTER, LEFT, CENTER, CENTER, CENTER]
        for ci, (v, al) in enumerate(zip(fixed_vals, fixed_als), 1):
            c = ws3.cell(row=er, column=ci, value=v)
            c.font = cell_font(); c.fill = rf; c.alignment = al; c.border = thin_border()

        row_total = 0
        for d in range(1, days_in_month + 1):
            qty = row["days"].get(d, 0)
            ci = d + 5
            c = ws3.cell(row=er, column=ci, value=qty if qty > 0 else None)
            c.fill = rf
            c.alignment = CENTER
            c.border = thin_border()
            if qty > 0:
                c.font = cell_font(bold=True, color="154360")
            else:
                c.font = Font(name="Calibri", size=9, color=ZERO_COLOR)
                c.value = "-"
            row_total += qty
            day_col_totals[d] += qty

        # Row total & kgs
        row_kgs = round(row_total * row["weight"], 2)
        tot_ci = 5 + days_in_month + 1
        c = ws3.cell(row=er, column=tot_ci, value=row_total)
        c.font = Font(name="Calibri", bold=True, size=10, color="1A5276")
        c.fill = ALT1_FILL; c.alignment = CENTER; c.border = thin_border()

        kgs_ci = 5 + days_in_month + 2
        c = ws3.cell(row=er, column=kgs_ci, value=row_kgs)
        c.font = cell_font(bold=True); c.fill = rf; c.alignment = CENTER; c.border = thin_border()

        grand_tot3 += row_total; grand_kgs3 += row_kgs

    # Footer row
    fr3 = len(rows) + 4
    ws3.row_dimensions[fr3].height = 20
    for ci in range(1, total_cols + 1):
        c = ws3.cell(row=fr3, column=ci)
        c.fill = FOOT_FILL; c.border = thin_border()

    ws3.cell(row=fr3, column=1, value="TOTAL").font = hdr_font()
    ws3.cell(row=fr3, column=1).alignment = CENTER

    for d in range(1, days_in_month + 1):
        ci = d + 5
        v = day_col_totals[d]
        c = ws3.cell(row=fr3, column=ci, value=v if v > 0 else None)
        c.font = hdr_font(size=9); c.alignment = CENTER; c.border = thin_border()

    c = ws3.cell(row=fr3, column=5 + days_in_month + 1, value=grand_tot3)
    c.font = hdr_font(); c.alignment = CENTER

    c = ws3.cell(row=fr3, column=5 + days_in_month + 2, value=round(grand_kgs3, 2))
    c.font = hdr_font(); c.alignment = CENTER

    # ── Freeze panes ────────────────────────────────────────────────────────
    ws1.freeze_panes = "A4"
    ws2.freeze_panes = "A4"
    ws3.freeze_panes = "F4"

    # ── Output ──────────────────────────────────────────────────────────────
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename_label = label.replace(" ", "_")
    response = HttpResponse(
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="CYCLE_TUBE_PRODUCTION_{filename_label}.xlsx"'
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
