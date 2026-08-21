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
            ).aggregate(total=Sum("quantity"))["total"]
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
        ).values_list("date", flat=True)
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
        ).select_related("tube_item")

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
