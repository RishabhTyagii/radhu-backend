import re
import datetime
from django.db import transaction
from django.db.models import Sum, Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
import openpyxl

from .models import TyreItem, DailyEntry, DailyProductionManualEntry
from .serializers import TyreItemSerializer, DailyEntrySerializer, DailyProductionManualEntrySerializer

def _recalculate_auto_stocks():
    for item in TyreItem.objects.all():
        p1 = DailyEntry.objects.filter(tyre_item=item, entry_type="production", bucket="stock").aggregate(t=Sum("quantity"))["t"] or 0
        s1 = DailyEntry.objects.filter(tyre_item=item, entry_type="dispatch", bucket="stock").aggregate(t=Sum("quantity"))["t"] or 0
        a1 = DailyEntry.objects.filter(tyre_item=item, entry_type="adjustment", bucket="stock").aggregate(t=Sum("quantity"))["t"] or 0

        p2 = DailyEntry.objects.filter(tyre_item=item, entry_type="production").aggregate(t=Sum("second_grade"))["t"] or 0
        s2 = DailyEntry.objects.filter(tyre_item=item, entry_type="dispatch", bucket="second_stock").aggregate(t=Sum("quantity"))["t"] or 0
        a2 = DailyEntry.objects.filter(tyre_item=item, entry_type="adjustment", bucket="second_stock").aggregate(t=Sum("quantity"))["t"] or 0

        p3 = DailyEntry.objects.filter(tyre_item=item, entry_type="production").aggregate(t=Sum("third_grade"))["t"] or 0
        s3 = DailyEntry.objects.filter(tyre_item=item, entry_type="dispatch", bucket="third_stock").aggregate(t=Sum("quantity"))["t"] or 0
        a3 = DailyEntry.objects.filter(tyre_item=item, entry_type="adjustment", bucket="third_stock").aggregate(t=Sum("quantity"))["t"] or 0

        p_rfm = DailyEntry.objects.filter(tyre_item=item, entry_type="production", bucket="rfm_ok_tyre").aggregate(t=Sum("quantity"))["t"] or 0
        s_rfm = DailyEntry.objects.filter(tyre_item=item, entry_type="dispatch", bucket="rfm_ok_tyre").aggregate(t=Sum("quantity"))["t"] or 0
        a_rfm = DailyEntry.objects.filter(tyre_item=item, entry_type="adjustment", bucket="rfm_ok_tyre").aggregate(t=Sum("quantity"))["t"] or 0

        item.stock = p1 - s1 + a1
        item.second_stock = p2 - s2 + a2
        item.third_stock = p3 - s3 + a3
        item.rfm_ok_tyre = p_rfm - s_rfm + a_rfm
        item.save(update_fields=["stock", "second_stock", "third_stock", "rfm_ok_tyre"])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    _recalculate_auto_stocks()

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

    items = TyreItem.objects.filter(is_active=True)
    items_data = []

    tot_prev_first = 0
    tot_prev_second = 0
    tot_prev_third = 0
    tot_prod_total = 0
    tot_prod_first = 0
    tot_prod_second = 0
    tot_prod_third = 0
    tot_sale_first = 0
    tot_sale_second = 0
    tot_sale_third = 0
    tot_rfm = 0
    tot_closing_first = 0
    tot_closing_second = 0
    tot_closing_third = 0
    tot_total_closing = 0

    for item in items:
        if is_filtered_range and filter_start and filter_end:
            # Previous closing (before start date)
            p1_prev = DailyEntry.objects.filter(
                tyre_item=item, entry_type="production", bucket="stock", date__lt=filter_start
            ).aggregate(t=Sum("quantity"))["t"] or 0
            s1_prev = DailyEntry.objects.filter(
                tyre_item=item, entry_type="dispatch", bucket="stock", date__lt=filter_start
            ).aggregate(t=Sum("quantity"))["t"] or 0
            a1_prev = DailyEntry.objects.filter(
                tyre_item=item, entry_type="adjustment", bucket="stock", date__lt=filter_start
            ).aggregate(t=Sum("quantity"))["t"] or 0

            p2_prev = DailyEntry.objects.filter(
                tyre_item=item, entry_type="production", date__lt=filter_start
            ).aggregate(t=Sum("second_grade"))["t"] or 0
            s2_prev = DailyEntry.objects.filter(
                tyre_item=item, entry_type="dispatch", bucket="second_stock", date__lt=filter_start
            ).aggregate(t=Sum("quantity"))["t"] or 0
            a2_prev = DailyEntry.objects.filter(
                tyre_item=item, entry_type="adjustment", bucket="second_stock", date__lt=filter_start
            ).aggregate(t=Sum("quantity"))["t"] or 0

            p3_prev = DailyEntry.objects.filter(
                tyre_item=item, entry_type="production", date__lt=filter_start
            ).aggregate(t=Sum("third_grade"))["t"] or 0
            s3_prev = DailyEntry.objects.filter(
                tyre_item=item, entry_type="dispatch", bucket="third_stock", date__lt=filter_start
            ).aggregate(t=Sum("quantity"))["t"] or 0
            a3_prev = DailyEntry.objects.filter(
                tyre_item=item, entry_type="adjustment", bucket="third_stock", date__lt=filter_start
            ).aggregate(t=Sum("quantity"))["t"] or 0

            prev_first = p1_prev - s1_prev + a1_prev
            prev_second = p2_prev - s2_prev + a2_prev
            prev_third = p3_prev - s3_prev + a3_prev

            # In-range production
            range_prod = DailyEntry.objects.filter(
                tyre_item=item, entry_type="production", date__gte=filter_start, date__lte=filter_end
            )
            p1_range = range_prod.filter(bucket="stock").aggregate(t=Sum("quantity"))["t"] or 0
            p2_range = range_prod.aggregate(t=Sum("second_grade"))["t"] or 0
            p3_range = range_prod.aggregate(t=Sum("third_grade"))["t"] or 0

            # In-range sales / dispatches
            s1_range = DailyEntry.objects.filter(
                tyre_item=item, entry_type="dispatch", bucket="stock", date__gte=filter_start, date__lte=filter_end
            ).aggregate(t=Sum("quantity"))["t"] or 0
            s2_range = DailyEntry.objects.filter(
                tyre_item=item, entry_type="dispatch", bucket="second_stock", date__gte=filter_start, date__lte=filter_end
            ).aggregate(t=Sum("quantity"))["t"] or 0
            s3_range = DailyEntry.objects.filter(
                tyre_item=item, entry_type="dispatch", bucket="third_stock", date__gte=filter_start, date__lte=filter_end
            ).aggregate(t=Sum("quantity"))["t"] or 0

            # In-range adjustments
            a1_range = DailyEntry.objects.filter(
                tyre_item=item, entry_type="adjustment", bucket="stock", date__gte=filter_start, date__lte=filter_end
            ).aggregate(t=Sum("quantity"))["t"] or 0
            a2_range = DailyEntry.objects.filter(
                tyre_item=item, entry_type="adjustment", bucket="second_stock", date__gte=filter_start, date__lte=filter_end
            ).aggregate(t=Sum("quantity"))["t"] or 0
            a3_range = DailyEntry.objects.filter(
                tyre_item=item, entry_type="adjustment", bucket="third_stock", date__gte=filter_start, date__lte=filter_end
            ).aggregate(t=Sum("quantity"))["t"] or 0

            closing_first = prev_first + p1_range - s1_range + a1_range
            closing_second = prev_second + p2_range - s2_range + a2_range
            closing_third = prev_third + p3_range - s3_range + a3_range
            rfm = item.rfm_ok_tyre
            total_closing = closing_first + closing_second + closing_third + rfm

            prod_first = p1_range
            prod_second = p2_range
            prod_third = p3_range
            prod_total = p1_range + p2_range + p3_range

            sale_first = s1_range
            sale_second = s2_range
            sale_third = s3_range

        else:
            # All time
            prev_first = 0
            prev_second = 0
            prev_third = 0

            all_prod = DailyEntry.objects.filter(tyre_item=item, entry_type="production")
            prod_first = all_prod.filter(bucket="stock").aggregate(t=Sum("quantity"))["t"] or 0
            prod_second = all_prod.aggregate(t=Sum("second_grade"))["t"] or 0
            prod_third = all_prod.aggregate(t=Sum("third_grade"))["t"] or 0
            prod_total = prod_first + prod_second + prod_third

            sale_first = DailyEntry.objects.filter(tyre_item=item, entry_type="dispatch", bucket="stock").aggregate(t=Sum("quantity"))["t"] or 0
            sale_second = DailyEntry.objects.filter(tyre_item=item, entry_type="dispatch", bucket="second_stock").aggregate(t=Sum("quantity"))["t"] or 0
            sale_third = DailyEntry.objects.filter(tyre_item=item, entry_type="dispatch", bucket="third_stock").aggregate(t=Sum("quantity"))["t"] or 0

            closing_first = item.stock
            closing_second = item.second_stock
            closing_third = item.third_stock
            rfm = item.rfm_ok_tyre
            total_closing = closing_first + closing_second + closing_third + rfm

        serialized = TyreItemSerializer(item).data
        serialized.update({
            "prev_closing_first": prev_first,
            "prev_closing_second": prev_second,
            "prev_closing_third": prev_third,
            "month_prod_total": prod_total,
            "month_prod_first": prod_first,
            "month_prod_second": prod_second,
            "month_prod_third": prod_third,
            "month_sale_first": sale_first,
            "month_sale_second": sale_second,
            "month_sale_third": sale_third,
            "rfm_ok_tyre": rfm,
            "closing_first": closing_first,
            "closing_second": closing_second,
            "closing_third": closing_third,
            "total_closing": total_closing,
        })
        items_data.append(serialized)

        tot_prev_first += prev_first
        tot_prev_second += prev_second
        tot_prev_third += prev_third
        tot_prod_total += prod_total
        tot_prod_first += prod_first
        tot_prod_second += prod_second
        tot_prod_third += prod_third
        tot_sale_first += sale_first
        tot_sale_second += sale_second
        tot_sale_third += sale_third
        tot_rfm += rfm
        tot_closing_first += closing_first
        tot_closing_second += closing_second
        tot_closing_third += closing_third
        tot_total_closing += total_closing

    # Available months list
    entry_dates = DailyEntry.objects.dates("date", "month", order="DESC")
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

    today_prod_all = DailyEntry.objects.filter(
        entry_type="production", date=today
    ).exclude(bucket="rfm_ok_tyre").aggregate(
        q=Sum("quantity"), s=Sum("second_grade"), t=Sum("third_grade")
    )
    today_prod_count = (today_prod_all["q"] or 0) + (today_prod_all["s"] or 0) + (today_prod_all["t"] or 0)
    today_disp_count = DailyEntry.objects.filter(entry_type="dispatch", date=today).aggregate(Sum("quantity"))["quantity__sum"] or 0

    return Response({
        "selected_month": month_param or "custom",
        "start_date": str(filter_start) if filter_start else None,
        "end_date": str(filter_end) if filter_end else None,
        "available_months": available_months,
        "stats": {
            "today_production": today_prod_count,
            "today_dispatch": today_disp_count,
            "month_prod_total": tot_prod_total,
            "month_prod_first": tot_prod_first,
            "month_prod_second": tot_prod_second,
            "month_prod_third": tot_prod_third,
            "month_sale_first": tot_sale_first,
            "closing_first": tot_closing_first,
            "closing_second": tot_closing_second,
            "closing_third": tot_closing_third,
            "total_closing": tot_total_closing,
        },
        "totals": {
            "prev_closing_first": tot_prev_first,
            "prev_closing_second": tot_prev_second,
            "prev_closing_third": tot_prev_third,
            "month_prod_total": tot_prod_total,
            "month_prod_first": tot_prod_first,
            "month_prod_second": tot_prod_second,
            "month_prod_third": tot_prod_third,
            "month_sale_first": tot_sale_first,
            "month_sale_second": tot_sale_second,
            "month_sale_third": tot_sale_third,
            "rfm_ok_tyre": tot_rfm,
            "closing_first": tot_closing_first,
            "closing_second": tot_closing_second,
            "closing_third": tot_closing_third,
            "total_closing": tot_total_closing,
        },
        "items": items_data,
    })

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_tyre(request):
    serializer = TyreItemSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tyres_list(request):
    items = TyreItem.objects.filter(is_active=True)
    serializer = TyreItemSerializer(items, many=True)
    return Response(serializer.data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_production(request):
    data = request.data
    tyre_id = data.get("tyre_item")
    try:
        item = TyreItem.objects.get(id=tyre_id)
    except TyreItem.DoesNotExist:
        return Response({"error": "Tyre not found"}, status=status.HTTP_404_NOT_FOUND)

    all_curing = int(data.get("all_curing", 0))
    production_tyre = int(data.get("production_tyre", 0))
    repair = int(data.get("repair", 0))
    second_grade = int(data.get("second_grade", 0))
    third_grade = int(data.get("third_grade", 0))
    lose_tyre = int(data.get("lose_tyre", 0))
    
    packing = (all_curing + repair + production_tyre) - (second_grade + third_grade + lose_tyre)
    if packing < 0:
        return Response({"error": "Packing quantity cannot be negative"}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        item.stock += packing
        item.second_stock += second_grade
        item.third_stock += third_grade
        item.save(update_fields=["stock", "second_stock", "third_stock"])

        entry = DailyEntry.objects.create(
            tyre_item=item,
            entry_type="production",
            bucket="stock",
            quantity=packing,
            date=data.get("date"),
            all_curing=all_curing,
            production_tyre=production_tyre,
            repair=repair,
            second_grade=second_grade,
            third_grade=third_grade,
            lose_tyre=lose_tyre,
            actual_weight=data.get("actual_weight") or None,
            remark=data.get("remark", ""),
            user=request.user
        )

    return Response({"message": "Production added successfully", "packing": packing})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recent_production(request):
    entries = DailyEntry.objects.filter(entry_type="production").select_related("tyre_item", "user")[:15]
    serializer = DailyEntrySerializer(entries, many=True)
    return Response(serializer.data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_dispatch(request):
    data = request.data
    tyre_id = data.get("tyre_item")
    try:
        item = TyreItem.objects.get(id=tyre_id)
    except TyreItem.DoesNotExist:
        return Response({"error": "Tyre not found"}, status=status.HTTP_404_NOT_FOUND)

    bill_number = data.get("bill_number", "").strip()
    if bill_number:
        if DailyEntry.objects.filter(entry_type="dispatch", bill_number__iexact=bill_number).exists():
            return Response({"error": "Duplicate bill number"}, status=status.HTTP_400_BAD_REQUEST)

    bucket = data.get("bucket", "stock")
    qty = int(data.get("quantity", 0))
    current = getattr(item, bucket)

    if qty > current:
        return Response({"error": f"sirf {current} available hai"}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        setattr(item, bucket, current - qty)
        item.save(update_fields=[bucket])

        DailyEntry.objects.create(
            tyre_item=item,
            entry_type="dispatch",
            bucket=bucket,
            quantity=qty,
            date=data.get("date"),
            bill_number=bill_number,
            remark=data.get("remark", ""),
            user=request.user
        )

    return Response({"message": "Dispatch added successfully"})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def recent_dispatch(request):
    entries = DailyEntry.objects.filter(entry_type="dispatch").select_related("tyre_item", "user")[:15]
    serializer = DailyEntrySerializer(entries, many=True)
    return Response(serializer.data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_adjustment(request):
    data = request.data
    tyre_id = data.get("tyre_item")
    try:
        item = TyreItem.objects.get(id=tyre_id)
    except TyreItem.DoesNotExist:
        return Response({"error": "Tyre not found"}, status=status.HTTP_404_NOT_FOUND)

    bucket = data.get("bucket", "stock")
    action = data.get("action")
    qty = int(data.get("quantity", 0))
    current = getattr(item, bucket)

    if action == "subtract" and qty > current:
        return Response({"error": "Not enough stock for adjustment"}, status=status.HTTP_400_BAD_REQUEST)

    signed_qty = qty if action == "add" else -qty

    with transaction.atomic():
        setattr(item, bucket, current + signed_qty)
        item.save(update_fields=[bucket])

        DailyEntry.objects.create(
            tyre_item=item,
            entry_type="adjustment",
            bucket=bucket,
            quantity=signed_qty,
            date=data.get("date"),
            remark=data.get("remark", ""),
            user=request.user
        )

    return Response({"message": "Adjustment successful"})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def entries_log(request):
    date_param = request.GET.get("date")
    month_param = request.GET.get("month")
    entry_type = request.GET.get("type")
    tyre_id = request.GET.get("tyre_id")
    search_q = request.GET.get("search")

    entries = DailyEntry.objects.all()

    if date_param:
        entries = entries.filter(date=date_param)
    elif month_param:
        try:
            year, month = month_param.split("-")
            entries = entries.filter(date__year=year, date__month=month)
        except:
            pass

    if entry_type:
        entries = entries.filter(entry_type=entry_type)
        
    if tyre_id:
        entries = entries.filter(tyre_item_id=tyre_id)
        
    if search_q:
        from django.db.models import Q
        entries = entries.filter(
            Q(remark__icontains=search_q) |
            Q(bill_number__icontains=search_q) |
            Q(tyre_item__tyre__icontains=search_q) |
            Q(tyre_item__pattern__icontains=search_q)
        )

    entries = entries.select_related("tyre_item", "user")[:500]
    serializer = DailyEntrySerializer(entries, many=True)
    return Response(serializer.data)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_report(request):
    month_param = request.GET.get("month")
    today = datetime.date.today()
    if month_param:
        try:
            year, month = map(int, month_param.split("-"))
            target_date = datetime.date(year, month, 1)
        except:
            target_date = today.replace(day=1)
    else:
        target_date = today.replace(day=1)

    items = TyreItem.objects.filter(is_active=True)
    report_items = []

    total_curing = 0
    total_despatch = 0

    for item in items:
        prod = DailyEntry.objects.filter(tyre_item=item, entry_type="production", date__year=target_date.year, date__month=target_date.month).aggregate(Sum("quantity"))['quantity__sum'] or 0
        disp = DailyEntry.objects.filter(tyre_item=item, entry_type="dispatch", date__year=target_date.year, date__month=target_date.month).aggregate(Sum("quantity"))['quantity__sum'] or 0

        if prod > 0 or disp > 0:
            report_items.append({
                "tyre_id": item.id,
                "tyre_name": item.tyre,
                "pattern": item.pattern,
                "type": item.type,
                "monthly_curing": prod,
                "monthly_despatch": disp
            })
            total_curing += prod
            total_despatch += disp

    grand_total_stock = sum(item.total_stock for item in items)
    net_balance = total_curing - total_despatch

    trend_data = []
    for i in range(5, -1, -1):
        m = target_date.month - i
        y = target_date.year
        if m <= 0:
            m += 12
            y -= 1
        
        prod = DailyEntry.objects.filter(entry_type="production", date__year=y, date__month=m).aggregate(Sum("quantity"))['quantity__sum'] or 0
        disp = DailyEntry.objects.filter(entry_type="dispatch", date__year=y, date__month=m).aggregate(Sum("quantity"))['quantity__sum'] or 0
        
        month_label = datetime.date(y, m, 1).strftime("%b %Y")
        trend_data.append({
            "month": month_label,
            "production": prod,
            "dispatch": disp
        })

    return Response({
        "items": report_items,
        "totals": {
            "total_curing": total_curing,
            "total_despatch": total_despatch,
            "net_balance": net_balance,
            "grand_total_stock": grand_total_stock,
        },
        "trend": trend_data
    })


def sku_sort_key(sku, fallback=""):
    """
    Sorts codes alphanumerically like 1..100, AT1..AT20, etc.
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
    date_param = request.GET.get("date")
    month_param = request.GET.get("month")
    
    if date_param:
        entries = DailyEntry.objects.filter(entry_type="production", date=date_param).exclude(bucket="rfm_ok_tyre").select_related("tyre_item")
    elif month_param:
        try:
            year, month = month_param.split("-")
            entries = DailyEntry.objects.filter(entry_type="production", date__year=year, date__month=month).exclude(bucket="rfm_ok_tyre").select_related("tyre_item")
        except:
            today = datetime.date.today()
            entries = DailyEntry.objects.filter(entry_type="production", date__year=today.year, date__month=today.month).exclude(bucket="rfm_ok_tyre").select_related("tyre_item")
    else:
        today = datetime.date.today()
        entries = DailyEntry.objects.filter(entry_type="production", date__year=today.year, date__month=today.month).exclude(bucket="rfm_ok_tyre").select_related("tyre_item")

    data_list = []
    
    totals = {
        "all_curing": 0, "production_tyre": 0, "repair": 0, "second_grade": 0, 
        "third_grade": 0, "lose_tyre": 0, "packing": 0, "rfm_adjustment": 0
    }
    
    labels = []
    curing_data = []
    packing_data = []
    repair_data = []
    second_data = []
    third_data = []
    lose_data = []
    
    if date_param:
        for entry in entries:
            rfm = DailyEntry.objects.filter(entry_type="adjustment", bucket="rfm_ok_tyre", date=entry.date, tyre_item=entry.tyre_item).aggregate(Sum("quantity"))['quantity__sum'] or 0
            data_list.append({
                "sku": entry.tyre_item.sku or "",
                "tyre_name": str(entry.tyre_item),
                "all_curing": entry.all_curing,
                "production_tyre": entry.production_tyre,
                "repair": entry.repair,
                "second_grade": entry.second_grade,
                "third_grade": entry.third_grade,
                "lose_tyre": entry.lose_tyre,
                "packing": entry.quantity,
                "rfm_adjustment": rfm
            })
            totals["all_curing"] += entry.all_curing
            totals["production_tyre"] += entry.production_tyre
            totals["repair"] += entry.repair
            totals["second_grade"] += entry.second_grade
            totals["third_grade"] += entry.third_grade
            totals["lose_tyre"] += entry.lose_tyre
            totals["packing"] += entry.quantity
            totals["rfm_adjustment"] += rfm
    else:
        # aggregate by tyre item
        tyre_aggregates = {}
        for entry in entries:
            tid = entry.tyre_item.id
            if tid not in tyre_aggregates:
                tyre_aggregates[tid] = {
                    "sku": entry.tyre_item.sku or "",
                    "tyre_name": str(entry.tyre_item),
                    "all_curing": 0,
                    "production_tyre": 0,
                    "repair": 0,
                    "second_grade": 0,
                    "third_grade": 0,
                    "lose_tyre": 0,
                    "packing": 0,
                    "rfm_adjustment": 0
                }
            
            tyre_aggregates[tid]["all_curing"] += entry.all_curing
            tyre_aggregates[tid]["production_tyre"] += entry.production_tyre
            tyre_aggregates[tid]["repair"] += entry.repair
            tyre_aggregates[tid]["second_grade"] += entry.second_grade
            tyre_aggregates[tid]["third_grade"] += entry.third_grade
            tyre_aggregates[tid]["lose_tyre"] += entry.lose_tyre
            tyre_aggregates[tid]["packing"] += entry.quantity

        # Aggregate monthly RFM adjustments
        today = datetime.date.today()
        if month_param:
            try:
                y, m = month_param.split("-")
                rfm_qs = DailyEntry.objects.filter(entry_type="adjustment", bucket="rfm_ok_tyre", date__year=y, date__month=m)
            except:
                rfm_qs = DailyEntry.objects.filter(entry_type="adjustment", bucket="rfm_ok_tyre", date__year=today.year, date__month=today.month)
        else:
            rfm_qs = DailyEntry.objects.filter(entry_type="adjustment", bucket="rfm_ok_tyre", date__year=today.year, date__month=today.month)

        for r_entry in rfm_qs:
            tid = r_entry.tyre_item_id
            if tid in tyre_aggregates:
                tyre_aggregates[tid]["rfm_adjustment"] += r_entry.quantity
            else:
                tyre_aggregates[tid] = {
                    "sku": r_entry.tyre_item.sku if r_entry.tyre_item else "",
                    "tyre_name": str(r_entry.tyre_item),
                    "all_curing": 0, "production_tyre": 0, "repair": 0,
                    "second_grade": 0, "third_grade": 0, "lose_tyre": 0,
                    "packing": 0, "rfm_adjustment": r_entry.quantity
                }
            
        for tid, agg in tyre_aggregates.items():
            data_list.append(agg)
            for k in totals.keys():
                totals[k] += agg.get(k, 0)
                
    data_list.sort(key=lambda x: sku_sort_key(x.get("sku", ""), x.get("tyre_name", "")))

    for agg in data_list:
        labels.append(agg["tyre_name"])
        curing_data.append(agg["all_curing"])
        packing_data.append(agg["packing"])
        repair_data.append(agg["repair"])
        second_data.append(agg["second_grade"])
        third_data.append(agg["third_grade"])
        lose_data.append(agg["lose_tyre"])
            
    return Response({
        "data": data_list,
        "totals": totals,
        "chart": {
            "labels": labels,
            "curing": curing_data,
            "values": packing_data,
            "repair": repair_data,
            "second": second_data,
            "third": third_data,
            "lose": lose_data
        }
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_production_sheet(request):
    """
    Export date-wise item production for Auto Tyre (3 sheets):
      1. Daily Matrix (1-31) - Calendar grid with 8 sub-columns per day
      2. Monthly Summary - Item consolidated totals with weights
      3. Date-Wise Production - Detailed daily ledger
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

    # Typography & Styles
    f_title = Font(name="Calibri", size=15, bold=True, color="FFFFFF")
    f_sub = Font(name="Calibri", size=10, bold=False, color="FFFFFF")
    f_heading = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    f_tbl_hdr = Font(name="Calibri", size=9, bold=True, color="FFFFFF")
    f_data = Font(name="Calibri", size=9)
    f_bold = Font(name="Calibri", size=9, bold=True)
    f_tot = Font(name="Calibri", size=10, bold=True, color="0F172A")

    fill_hdr = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    fill_sub = PatternFill(start_color="2D6A9F", end_color="2D6A9F", fill_type="solid")
    fill_day = PatternFill(start_color="154360", end_color="154360", fill_type="solid")
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_tot = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    al_center = Alignment(horizontal="center", vertical="center")
    al_left = Alignment(horizontal="left", vertical="center")
    al_right = Alignment(horizontal="right", vertical="center")

    thin = Side(border_style="thin", color="CBD5E1")
    double = Side(border_style="double", color="1E3A8A")
    border_cell = Border(left=thin, right=thin, top=thin, bottom=thin)
    border_tot = Border(left=thin, right=thin, top=thin, bottom=double)

    if is_single_date:
        entries_qs = DailyEntry.objects.filter(
            entry_type='production', date=date_param
        ).exclude(bucket='rfm_ok_tyre').select_related('tyre_item')
        rfm_qs = DailyEntry.objects.filter(
            entry_type='adjustment', bucket='rfm_ok_tyre', date=date_param
        )
    else:
        entries_qs = DailyEntry.objects.filter(
            entry_type='production', date__year=year, date__month=month
        ).exclude(bucket='rfm_ok_tyre').select_related('tyre_item')
        rfm_qs = DailyEntry.objects.filter(
            entry_type='adjustment', bucket='rfm_ok_tyre', date__year=year, date__month=month
        )

    entries = list(entries_qs)
    rfm_map = {}
    for r in rfm_qs:
        key = (r.date.day, r.tyre_item_id)
        rfm_map[key] = rfm_map.get(key, 0) + r.quantity

    all_items = sorted(
        TyreItem.objects.filter(is_active=True),
        key=lambda x: sku_sort_key(x.sku, f"{x.tyre} {x.pattern}")
    )

    prod_day_map = {}
    for e in entries:
        key = (e.tyre_item_id, e.date.day)
        if key not in prod_day_map:
            prod_day_map[key] = {
                "all_curing": 0, "production": 0, "repair": 0, "second": 0,
                "third": 0, "lose": 0, "packing": 0
            }
        prod_day_map[key]["all_curing"] += e.all_curing
        prod_day_map[key]["production"] += e.production_tyre
        prod_day_map[key]["repair"] += e.repair
        prod_day_map[key]["second"] += e.second_grade
        prod_day_map[key]["third"] += e.third_grade
        prod_day_map[key]["lose"] += e.lose_tyre
        prod_day_map[key]["packing"] += e.quantity

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ════════════════════════════════════════════════════════════════════════════════
    # SHEET 1: Daily Matrix (1-31)
    # ════════════════════════════════════════════════════════════════════════════════
    ws1 = wb.create_sheet("Daily Matrix (1-31)")
    ws1.views.sheetView[0].showGridLines = True

    sub_cols = ["Curing", "Prod", "Rep", "2nd", "3rd", "Lose", "RFM", "Pack"]
    num_sub = len(sub_cols)  # 8
    tot_start_col = 6 + num_days * num_sub
    last_col = tot_start_col + num_sub  # 8 metrics + Total Kgs = +8

    # Title Banner
    ws1.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    c1 = ws1.cell(1, 1, "RADHU INDUSTRIES")
    c1.font = f_title; c1.fill = fill_hdr; c1.alignment = al_center
    ws1.row_dimensions[1].height = 28

    ws1.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
    c2 = ws1.cell(2, 1, "17/5 MILE STONE DELHI MEERUT ROAD MURAD NAGAR U.P.-201206")
    c2.font = f_sub; c2.fill = fill_sub; c2.alignment = al_center
    ws1.row_dimensions[2].height = 18

    ws1.merge_cells(start_row=3, start_column=1, end_row=3, end_column=last_col)
    c3 = ws1.cell(3, 1, f"AUTOMOTIVE TYRE — DATE-WISE PRODUCTION MATRIX | {label}")
    c3.font = f_heading; c3.fill = fill_hdr; c3.alignment = al_center
    ws1.row_dimensions[3].height = 22

    # Row 4: Dates Header
    ws1.merge_cells("A4:E4")
    ws1.cell(4, 1, "ITEM DETAILS").font = f_tbl_hdr
    ws1.cell(4, 1).fill = fill_hdr; ws1.cell(4, 1).alignment = al_center

    for d in range(1, num_days + 1):
        sc = 6 + (d - 1) * num_sub
        ec = sc + num_sub - 1
        ws1.merge_cells(start_row=4, start_column=sc, end_row=4, end_column=ec)
        dt_cell = ws1.cell(4, sc, f"{d:02d}-{month_name[:3]}")
        dt_cell.font = f_tbl_hdr; dt_cell.fill = fill_day; dt_cell.alignment = al_center

    ws1.merge_cells(start_row=4, start_column=tot_start_col, end_row=4, end_column=last_col)
    tot_banner = ws1.cell(4, tot_start_col, "MONTHLY TOTALS")
    tot_banner.font = f_tbl_hdr; tot_banner.fill = fill_hdr; tot_banner.alignment = al_center

    # Row 5: Column Sub-headers
    ws1.row_dimensions[5].height = 20
    fixed_hdrs = ["#", "CODE", "TYRE ITEM", "PATTERN", "TYPE"]
    for ci, h in enumerate(fixed_hdrs, 1):
        c = ws1.cell(5, ci, h)
        c.font = f_tbl_hdr; c.fill = fill_hdr; c.alignment = al_center; c.border = border_cell

    for d in range(1, num_days + 1):
        sc = 6 + (d - 1) * num_sub
        for sub_idx, sub_label in enumerate(sub_cols):
            col = sc + sub_idx
            c = ws1.cell(5, col, sub_label)
            c.font = Font(name="Calibri", size=8, bold=True, color="FFFFFF")
            c.fill = fill_sub; c.alignment = al_center; c.border = border_cell

    for idx, h_tot in enumerate(["CURING", "PROD", "REPAIR", "2ND", "3RD", "LOSE", "RFM", "PACK", "TOTAL KGS"]):
        col = tot_start_col + idx
        c = ws1.cell(5, col, h_tot)
        c.font = f_tbl_hdr; c.fill = fill_hdr; c.alignment = al_center; c.border = border_cell

    # Fill Rows
    r_idx = 6
    for idx, item in enumerate(all_items, 1):
        rf = fill_zebra if idx % 2 == 0 else PatternFill("solid", fgColor="FFFFFF")
        ws1.row_dimensions[r_idx].height = 18

        ws1.cell(r_idx, 1, idx).alignment = al_center
        ws1.cell(r_idx, 2, item.sku or "").alignment = al_center
        ws1.cell(r_idx, 3, item.tyre or "").alignment = al_left
        ws1.cell(r_idx, 4, item.pattern or "").alignment = al_left
        ws1.cell(r_idx, 5, item.type or "").alignment = al_center

        for c in range(1, 6):
            cell = ws1.cell(r_idx, c)
            cell.font = f_bold if c == 2 else f_data
            cell.fill = rf; cell.border = border_cell

        for d in range(1, num_days + 1):
            sc = 6 + (d - 1) * num_sub
            pvals = prod_day_map.get((item.id, d), {})
            rfm_v = rfm_map.get((d, item.id), 0)

            day_vals = [
                pvals.get("all_curing", 0),
                pvals.get("production", 0),
                pvals.get("repair", 0),
                pvals.get("second", 0),
                pvals.get("third", 0),
                pvals.get("lose", 0),
                rfm_v,
                pvals.get("packing", 0),
            ]

            for s_idx, val in enumerate(day_vals):
                col = sc + s_idx
                cell_v = ws1.cell(r_idx, col, val if val > 0 else None)
                cell_v.alignment = al_right
                cell_v.border = border_cell
                cell_v.fill = rf
                if val > 0:
                    cell_v.font = Font(name="Calibri", size=9, bold=(s_idx in [0, 7]))

        # Row Totals for the 8 metrics
        for s_idx in range(num_sub):
            c_cells = [f"{get_column_letter(6 + (d - 1) * num_sub + s_idx)}{r_idx}" for d in range(1, num_days + 1)]
            col_tot = tot_start_col + s_idx
            c = ws1.cell(r_idx, col_tot, f"={'+'.join(c_cells)}")
            c.font = f_bold; c.alignment = al_right; c.border = border_cell; c.fill = fill_zebra

        # Total Kgs = Packing total * weight
        pack_col_let = get_column_letter(tot_start_col + 7)
        w_val = float(item.weight or 0)
        c_tot_kg = ws1.cell(r_idx, last_col, f"={pack_col_let}{r_idx}*{w_val}")
        c_tot_kg.font = f_bold; c_tot_kg.alignment = al_right; c_tot_kg.border = border_cell; c_tot_kg.fill = fill_zebra

        r_idx += 1

    # Footer Total Row
    foot_row = r_idx
    ws1.row_dimensions[foot_row].height = 22
    ws1.merge_cells(f"A{foot_row}:E{foot_row}")
    f_lbl = ws1.cell(foot_row, 1, "TOTAL PRODUCTION")
    f_lbl.font = f_tot; f_lbl.alignment = al_center; f_lbl.fill = fill_tot

    for col in range(1, last_col + 1):
        c = ws1.cell(foot_row, col)
        c.border = border_tot
        c.fill = fill_tot

    for col in range(6, last_col + 1):
        col_let = get_column_letter(col)
        c = ws1.cell(foot_row, col, f"=SUM({col_let}6:{col_let}{foot_row - 1})")
        c.font = f_tot; c.alignment = al_right

    ws1.column_dimensions["A"].width = 5
    ws1.column_dimensions["B"].width = 9   # CODE column
    ws1.column_dimensions["C"].width = 16
    ws1.column_dimensions["D"].width = 16
    ws1.column_dimensions["E"].width = 8

    for d in range(1, num_days + 1):
        sc = 6 + (d - 1) * num_sub
        for s_idx in range(num_sub):
            ws1.column_dimensions[get_column_letter(sc + s_idx)].width = 6

    for ci in range(tot_start_col, last_col + 1):
        ws1.column_dimensions[get_column_letter(ci)].width = 10

    # ════════════════════════════════════════════════════════════════════════════════
    # SHEET 2: Monthly Summary
    # ════════════════════════════════════════════════════════════════════════════════
    ws2 = wb.create_sheet("Monthly Summary")
    ws2.views.sheetView[0].showGridLines = True

    ws2.merge_cells("A1:O1")
    c1 = ws2.cell(1, 1, "RADHU INDUSTRIES")
    c1.font = f_title; c1.fill = fill_hdr; c1.alignment = al_center
    ws2.row_dimensions[1].height = 28

    ws2.merge_cells("A2:O2")
    c2 = ws2.cell(2, 1, "17/5 MILE STONE DELHI MEERUT ROAD MURAD NAGAR U.P.-201206")
    c2.font = f_sub; c2.fill = fill_sub; c2.alignment = al_center
    ws2.row_dimensions[2].height = 18

    ws2.merge_cells("A3:O3")
    c3 = ws2.cell(3, 1, f"AUTOMOTIVE TYRE — MONTHLY PRODUCTION SUMMARY | {label}")
    c3.font = f_heading; c3.fill = fill_hdr; c3.alignment = al_center
    ws2.row_dimensions[3].height = 22

    sum_hdrs = [
        "#", "CODE", "TYRE ITEM", "PATTERN", "TYPE", "ALL CURING", "PRODUCTION", "REPAIR",
        "2ND GRADE", "3RD GRADE", "LOSE TYRE", "RFM ADJ", "PACKING", "WEIGHT (KG)", "TOTAL KGS"
    ]
    ws2.row_dimensions[5].height = 22
    for ci, h in enumerate(sum_hdrs, 1):
        c = ws2.cell(5, ci, h)
        c.font = f_tbl_hdr; c.fill = fill_hdr; c.alignment = al_center; c.border = border_cell

    # Aggregate totals by item
    item_agg = {}
    for item in all_items:
        item_agg[item.id] = {
            "all_curing": 0, "production": 0, "repair": 0, "second": 0,
            "third": 0, "lose": 0, "packing": 0, "rfm": 0
        }

    for e in entries:
        tid = e.tyre_item_id
        if tid in item_agg:
            item_agg[tid]["all_curing"] += e.all_curing
            item_agg[tid]["production"] += e.production_tyre
            item_agg[tid]["repair"] += e.repair
            item_agg[tid]["second"] += e.second_grade
            item_agg[tid]["third"] += e.third_grade
            item_agg[tid]["lose"] += e.lose_tyre
            item_agg[tid]["packing"] += e.quantity

    for (d, tid), qty in rfm_map.items():
        if tid in item_agg:
            item_agg[tid]["rfm"] += qty

    r2_idx = 6
    for idx, item in enumerate(all_items, 1):
        rf = fill_zebra if idx % 2 == 0 else PatternFill("solid", fgColor="FFFFFF")
        ws2.row_dimensions[r2_idx].height = 18
        agg = item_agg[item.id]
        w_val = float(item.weight or 0)

        vals2 = [
            idx,
            item.sku or "",
            item.tyre or "",
            item.pattern or "",
            item.type or "",
            agg["all_curing"] if agg["all_curing"] > 0 else None,
            agg["production"] if agg["production"] > 0 else None,
            agg["repair"] if agg["repair"] > 0 else None,
            agg["second"] if agg["second"] > 0 else None,
            agg["third"] if agg["third"] > 0 else None,
            agg["lose"] if agg["lose"] > 0 else None,
            agg["rfm"] if agg["rfm"] > 0 else None,
            agg["packing"] if agg["packing"] > 0 else None,
            w_val,
            f"=M{r2_idx}*N{r2_idx}"
        ]

        for ci, v in enumerate(vals2, 1):
            c = ws2.cell(r2_idx, ci, v)
            c.border = border_cell
            c.fill = rf
            c.font = f_bold if ci in [2, 6, 13, 15] else f_data
            c.alignment = al_center if ci in [1, 2, 5] else (al_left if ci in [3, 4] else al_right)

        r2_idx += 1

    ws2.merge_cells(f"A{r2_idx}:E{r2_idx}")
    t2_lbl = ws2.cell(r2_idx, 1, "TOTALS")
    t2_lbl.font = f_tot; t2_lbl.alignment = al_center; t2_lbl.fill = fill_tot

    for col in range(1, 16):
        c = ws2.cell(r2_idx, col)
        c.border = border_tot
        c.fill = fill_tot

    for col in range(6, 14):
        col_let = get_column_letter(col)
        c = ws2.cell(r2_idx, col, f"=SUM({col_let}6:{col_let}{r2_idx - 1})")
        c.font = f_tot; c.alignment = al_right

    ws2.cell(r2_idx, 15, f"=SUM(O6:O{r2_idx - 1})").font = f_tot
    ws2.cell(r2_idx, 15).alignment = al_right

    col_w2 = [5, 9, 16, 16, 8, 12, 12, 10, 11, 11, 11, 11, 11, 12, 14]
    for ci, w in enumerate(col_w2, 1):
        ws2.column_dimensions[get_column_letter(ci)].width = w

    # ════════════════════════════════════════════════════════════════════════════════
    # SHEET 3: Date-Wise Production (Detailed Ledger)
    # ════════════════════════════════════════════════════════════════════════════════
    ws3 = wb.create_sheet("Date-Wise Production")
    ws3.views.sheetView[0].showGridLines = True

    ws3.merge_cells("A1:O1")
    c1 = ws3.cell(1, 1, "RADHU INDUSTRIES")
    c1.font = f_title; c1.fill = fill_hdr; c1.alignment = al_center
    ws3.row_dimensions[1].height = 28

    ws3.merge_cells("A2:O2")
    c2 = ws3.cell(2, 1, "17/5 MILE STONE DELHI MEERUT ROAD MURAD NAGAR U.P.-201206")
    c2.font = f_sub; c2.fill = fill_sub; c2.alignment = al_center
    ws3.row_dimensions[2].height = 18

    ws3.merge_cells("A3:O3")
    c3 = ws3.cell(3, 1, f"AUTOMOTIVE TYRE — DAILY PRODUCTION LOG | {label}")
    c3.font = f_heading; c3.fill = fill_hdr; c3.alignment = al_center
    ws3.row_dimensions[3].height = 22

    led_hdrs = [
        "Date", "CODE", "Tyre Item", "Pattern", "Type", "All Curing", "Production", "Repair",
        "2nd Grade", "3rd Grade", "Lose Tyre", "RFM Adj", "Packing", "Weight (Kg)", "Total Kgs"
    ]
    ws3.row_dimensions[5].height = 22
    for ci, h in enumerate(led_hdrs, 1):
        c = ws3.cell(5, ci, h)
        c.font = f_tbl_hdr; c.fill = fill_hdr; c.alignment = al_center; c.border = border_cell

    sorted_entries = sorted(entries, key=lambda e: (e.date, sku_sort_key(e.tyre_item.sku if e.tyre_item else "", f"{e.tyre_item.tyre} {e.tyre_item.pattern}" if e.tyre_item else "")))
    r3_idx = 6
    for idx, e in enumerate(sorted_entries, 1):
        rf = fill_zebra if idx % 2 == 0 else PatternFill("solid", fgColor="FFFFFF")
        item = e.tyre_item
        w_val = float(item.weight or 0) if item else 0
        rfm_val = rfm_map.get((e.date.day, e.tyre_item_id), 0)

        vals3 = [
            e.date.strftime("%d-%m-%Y"),
            item.sku if item else "",
            item.tyre if item else "",
            item.pattern if item else "",
            item.type if item else "",
            e.all_curing,
            e.production_tyre,
            e.repair,
            e.second_grade,
            e.third_grade,
            e.lose_tyre,
            rfm_val,
            e.quantity,
            w_val,
            f"=M{r3_idx}*N{r3_idx}"
        ]

        for ci, v in enumerate(vals3, 1):
            c = ws3.cell(r3_idx, ci, v)
            c.border = border_cell
            c.fill = rf
            c.font = f_bold if ci in [2, 6, 13, 15] else f_data
            c.alignment = al_center if ci in [1, 2, 5] else (al_left if ci in [3, 4] else al_right)

        r3_idx += 1

    if sorted_entries:
        ws3.merge_cells(f"A{r3_idx}:E{r3_idx}")
        t3_lbl = ws3.cell(r3_idx, 1, "TOTAL")
        t3_lbl.font = f_tot; t3_lbl.alignment = al_center; t3_lbl.fill = fill_tot
        for col in range(1, 16):
            ws3.cell(r3_idx, col).border = border_tot
            ws3.cell(r3_idx, col).fill = fill_tot
        for col in range(6, 14):
            col_let = get_column_letter(col)
            c = ws3.cell(r3_idx, col, f"=SUM({col_let}6:{col_let}{r3_idx - 1})")
            c.font = f_tot; c.alignment = al_right
        ws3.cell(r3_idx, 15, f"=SUM(O6:O{r3_idx - 1})").font = f_tot
        ws3.cell(r3_idx, 15).alignment = al_right

    col_w3 = [12, 9, 16, 16, 8, 12, 12, 10, 11, 11, 11, 11, 11, 12, 14]
    for ci, w in enumerate(col_w3, 1):
        ws3.column_dimensions[get_column_letter(ci)].width = w

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"AUTO_TYRE_PRODUCTION_{year}_{month:02d}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response

production_sheet_export = export_production_sheet

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def daily_summary(request):
    from decimal import Decimal
    from rawmaterial.models import MixingEntry

    if request.method == "POST":
        data = request.data
        entry_date = data.get("entry_date")
        if not entry_date:
            return Response({"error": "entry_date is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        obj, created = DailyProductionManualEntry.objects.get_or_create(date=entry_date)
        if "parchi_kg" in data:
            try: obj.parchi_kg = Decimal(str(data.get("parchi_kg") or 0))
            except: pass
        if "wastage" in data:
            try: obj.wastage = Decimal(str(data.get("wastage") or 0))
            except: pass
            
        req_mixing = data.get("mixing_actual_compound")
        if req_mixing is not None and float(req_mixing or 0) > 0:
            obj.mixing_actual_compound = Decimal(str(req_mixing))
        elif not obj.mixing_actual_compound or obj.mixing_actual_compound == 0:
            m = MixingEntry.objects.filter(date=entry_date).first()
            if m:
                mix_val = (
                    (m.compound_auto_tyre or Decimal("0.00"))
                    + (m.compound_lcv_tyre or Decimal("0.00"))
                    + (m.compound_auto_calender or Decimal("0.00"))
                    + (m.compound_tractor or Decimal("0.00"))
                )
                if mix_val > 0:
                    obj.mixing_actual_compound = mix_val
        obj.save()
        return Response({"message": "Saved successfully", "date": entry_date})

    # GET method
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    
    today = datetime.date.today()
    if not from_date:
        from_date = today.replace(day=1)
    if not to_date:
        to_date = today
        
    entries = DailyEntry.objects.filter(
        entry_type="production", date__gte=from_date, date__lte=to_date
    ).exclude(bucket="rfm_ok_tyre").select_related("tyre_item")
    
    dates_data = {}
    for entry in entries:
        d = str(entry.date)
        if d not in dates_data:
            dates_data[d] = {
                "date": d,
                "curing": 0,
                "packing": 0,
                "theoretical_kg": 0
            }
        dates_data[d]["curing"] += entry.all_curing
        dates_data[d]["packing"] += entry.quantity
        dates_data[d]["theoretical_kg"] += float(entry.all_curing) * float(entry.tyre_item.weight)
        
    manual_entries = DailyProductionManualEntry.objects.filter(date__gte=from_date, date__lte=to_date)
    manual_dict = {str(me.date): me for me in manual_entries}

    mixing_entries = MixingEntry.objects.filter(date__gte=from_date, date__lte=to_date)
    mixing_dict = {str(m.date): m for m in mixing_entries}
    
    all_dates = sorted(list(set(dates_data.keys()).union(set(manual_dict.keys())).union(set(mixing_dict.keys()))), reverse=True)
    
    results = []
    COMPOUND_PERCENT = 0.877
    
    for d in all_dates:
        data = dates_data.get(d, {
            "date": d,
            "curing": 0,
            "packing": 0,
            "theoretical_kg": 0
        })
        me = manual_dict.get(d)
        m = mixing_dict.get(d)
        
        parchi_kg = float(me.parchi_kg) if me else 0.0
        wastage = float(me.wastage) if me else 0.0
        
        # Calculate mixing compound from Compound Mixing Sheet:
        # PROJECT_MAP Rule: Auto Tyre Daily Summary: mixing_actual_compound = Auto Tyre + LCV Tyre + Auto Calender + Tractor (COMPOUND SIDE)
        mixing_from_sheet = 0.0
        if m:
            mixing_from_sheet = float(
                (m.compound_auto_tyre or 0)
                + (m.compound_lcv_tyre or 0)
                + (m.compound_auto_calender or 0)
                + (m.compound_tractor or 0)
            )
            
        manual_mixing = float(me.mixing_actual_compound) if me else 0.0
        
        if mixing_from_sheet > 0:
            mixing_actual = mixing_from_sheet
            if me and me.mixing_actual_compound != Decimal(str(round(mixing_from_sheet, 2))):
                me.mixing_actual_compound = Decimal(str(round(mixing_from_sheet, 2)))
                me.save()
        else:
            mixing_actual = manual_mixing
        
        theoretical_kg = data["theoretical_kg"]
        difference = parchi_kg - theoretical_kg  
        theoretical_total_compound = theoretical_kg * COMPOUND_PERCENT
        variance = mixing_actual - theoretical_total_compound
        
        results.append({
            "date": d,
            "curing": data["curing"],
            "packing": data["packing"],
            "theoretical_kg": round(theoretical_kg, 2),
            "parchi_kg": round(parchi_kg, 2),
            "difference": round(difference, 2),
            "theoretical_compound": round(theoretical_total_compound, 2),
            "mixing_actual_compound": round(mixing_actual, 2),
            "variance": round(variance, 2),
            "wastage": round(wastage, 2)
        })
        
    return Response(results)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_production_excel(request):
    import openpyxl

    file_obj = request.FILES.get("file") or request.FILES.get("excel_file")
    if not file_obj:
        return Response({"error": "No file uploaded. Please select an Excel file."}, status=status.HTTP_400_BAD_REQUEST)

    clear_existing = str(request.data.get("clear_existing", "true")).lower() in ["true", "1", "yes"]

    import_date_str = request.data.get("import_date") or request.data.get("date")
    user_date = None
    if import_date_str:
        try:
            user_date = datetime.datetime.strptime(str(import_date_str).strip(), "%Y-%m-%d").date()
        except ValueError:
            pass

    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
        ws = wb.active
    except Exception as e:
        return Response({"error": f"Failed to open Excel file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def safe_int(v):
        if v is None: return 0
        try: return int(float(v))
        except: return 0

    data_rows = []
    for r in range(2, ws.max_row + 1):
        tyre_name = ws.cell(row=r, column=1).value or ws.cell(row=r, column=2).value
        if not tyre_name or str(tyre_name).strip().lower() in ["total", "totals", "tyre", "size"]:
            continue

        curing = safe_int(ws.cell(row=r, column=3).value or ws.cell(row=r, column=4).value)
        prod = safe_int(ws.cell(row=r, column=5).value)
        repair = safe_int(ws.cell(row=r, column=6).value)
        second = safe_int(ws.cell(row=r, column=7).value)
        third = safe_int(ws.cell(row=r, column=8).value)
        lose = safe_int(ws.cell(row=r, column=9).value)

        if curing <= 0 and prod <= 0:
            continue

        data_rows.append({
            'row_num': r,
            'name': str(tyre_name).strip(),
            'all_curing': curing,
            'production_tyre': prod,
            'repair': repair,
            'second_grade': second,
            'third_grade': third,
            'lose_tyre': lose,
        })

    if not data_rows:
        return Response({"error": "No valid Auto Tyre production data found in Excel sheet."}, status=status.HTTP_400_BAD_REQUEST)

    entry_date = user_date or datetime.date.today()

    with transaction.atomic():
        if clear_existing:
            DailyEntry.objects.filter(entry_type="production").delete()
            TyreItem.objects.all().update(stock=0, repair_tyre_stock=0, rfm_ok_tyre=0)

        created_count = 0
        total_curing_imported = 0
        total_packing_imported = 0

        for row in data_rows:
            raw_name = row['name']
            item = TyreItem.objects.filter(tyre__iexact=raw_name).first()
            if not item:
                parts = raw_name.split()
                size = parts[0] if parts else raw_name
                pattern = " ".join(parts[1:-1]) if len(parts) > 2 else (parts[1] if len(parts) > 1 else "DEFAULT")
                ttype = parts[-1] if len(parts) > 1 and parts[-1].upper() in ["TL", "TT"] else "TT"
                item, _ = TyreItem.objects.get_or_create(
                    tyre=size, pattern=pattern, type=ttype,
                    defaults={"stock": 0, "is_active": True}
                )

            all_curing = row['all_curing']
            repair = row['repair']
            prod_tyre = row['production_tyre']
            second = row['second_grade']
            third = row['third_grade']
            lose = row['lose_tyre']

            packing = (all_curing + repair + prod_tyre) - (second + third + lose)
            if packing < 0:
                packing = 0

            item.stock += packing
            item.save(update_fields=["stock"])

            DailyEntry.objects.create(
                tyre_item=item,
                entry_type="production",
                bucket="stock",
                quantity=packing,
                date=entry_date,
                all_curing=all_curing,
                production_tyre=prod_tyre,
                repair=repair,
                second_grade=second,
                third_grade=third,
                lose_tyre=lose,
                remark="Excel Bulk Import",
                user=request.user
            )

            created_count += 1
            total_curing_imported += all_curing
            total_packing_imported += packing

    return Response({
        "ok": True,
        "message": f"Successfully imported {created_count} production entries.",
        "created_entries": created_count,
        "total_curing": total_curing_imported,
        "total_packing": total_packing_imported,
        "entry_date": str(entry_date)
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transactions_ledger(request):
    """
    Bank Passbook / Stock Ledger statement for Auto Tyre items.
    Calculates Opening Balance, Inflows (Production), Outflows (Dispatch),
    Adjustments, and Running Balance.
    """
    today = datetime.date.today()
    item_id_param = request.query_params.get("tyre_item") or request.query_params.get("item_id")
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

    all_items = TyreItem.objects.filter(is_active=True).order_by("tyre", "pattern")
    items_list = [
        {
            "id": it.id,
            "name": str(it),
            "tyre": it.tyre,
            "pattern": it.pattern,
            "type": it.type,
            "stock": it.stock,
            "second_stock": it.second_stock,
            "third_stock": it.third_stock,
            "repair_tyre_stock": it.repair_tyre_stock,
            "rfm_ok_tyre": it.rfm_ok_tyre,
            "total_stock": it.total_stock,
        }
        for it in all_items
    ]

    selected_item = None
    selected_item_obj = None
    if item_id_param and item_id_param != "all":
        try:
            selected_item_obj = TyreItem.objects.get(pk=int(item_id_param))
            selected_item = {
                "id": selected_item_obj.id,
                "name": str(selected_item_obj),
                "tyre": selected_item_obj.tyre,
                "pattern": selected_item_obj.pattern,
                "type": selected_item_obj.type,
                "stock": selected_item_obj.stock,
                "second_stock": selected_item_obj.second_stock,
                "third_stock": selected_item_obj.third_stock,
                "total_stock": selected_item_obj.total_stock,
            }
        except (TyreItem.DoesNotExist, ValueError):
            selected_item_obj = None
    elif item_id_param != "all":
        from django.db.models import Count
        most_active = DailyEntry.objects.values("tyre_item").annotate(c=Count("id")).order_by("-c").first()
        if most_active:
            try:
                selected_item_obj = TyreItem.objects.get(pk=most_active["tyre_item"])
            except:
                selected_item_obj = all_items.first()
        else:
            selected_item_obj = all_items.first()

        if selected_item_obj:
            selected_item = {
                "id": selected_item_obj.id,
                "name": str(selected_item_obj),
                "tyre": selected_item_obj.tyre,
                "pattern": selected_item_obj.pattern,
                "type": selected_item_obj.type,
                "stock": selected_item_obj.stock,
                "second_stock": selected_item_obj.second_stock,
                "third_stock": selected_item_obj.third_stock,
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

    prior_qs = DailyEntry.objects.filter(date__lt=from_date)
    period_qs = DailyEntry.objects.filter(date__gte=from_date, date__lte=to_date)

    if selected_item_obj:
        prior_qs = prior_qs.filter(tyre_item=selected_item_obj)
        period_qs = period_qs.filter(tyre_item=selected_item_obj)

    if bucket_param and bucket_param != "all":
        prior_qs = prior_qs.filter(bucket=bucket_param)
        period_qs = period_qs.filter(bucket=bucket_param)

    opening_balance = 0
    for e in prior_qs.order_by("date", "id"):
        if e.entry_type == "production":
            opening_balance += e.quantity
        elif e.entry_type == "dispatch":
            opening_balance -= e.quantity
        elif e.entry_type == "adjustment":
            opening_balance += e.quantity

    running_balance = opening_balance
    transactions = []
    total_in = 0
    total_out = 0

    period_entries = list(period_qs.select_related("tyre_item").order_by("date", "created_at", "id"))

    for e in period_entries:
        in_qty = 0
        out_qty = 0
        narration = ""
        party_name = extract_party(e.remark)

        if e.entry_type == "production":
            in_qty = e.quantity
            out_qty = 0
            narration = "Daily Production (Stock)"
            if e.remark:
                narration += f" — {e.remark}"
        elif e.entry_type == "dispatch":
            in_qty = 0
            out_qty = e.quantity
            narration = "Dispatch / Delivery"
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

        row_searchable = f"{e.date} {e.bill_number} {party_name} {e.remark} {narration} {str(e.tyre_item)}".lower()
        if search_q and search_q not in row_searchable:
            continue

        transactions.append({
            "id": e.id,
            "date": str(e.date),
            "created_at": e.created_at.strftime("%I:%M %p") if e.created_at else "",
            "entry_type": e.entry_type,
            "bucket": e.bucket,
            "bucket_display": e.get_bucket_display(),
            "tyre_item_id": e.tyre_item_id,
            "tyre_name": str(e.tyre_item),
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
def update_tyre_sku(request):
    """Update SKU number for a TyreItem."""
    item_id = request.data.get("id") or request.data.get("item_id")
    sku = (request.data.get("sku") or "").strip()
    if not item_id:
        return Response({"error": "Item ID is required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        item = TyreItem.objects.get(id=item_id)
        item.sku = sku
        item.save(update_fields=["sku"])
        return Response({
            "status": "success",
            "id": item.id,
            "sku": item.sku,
            "message": "SKU updated successfully."
        })
    except TyreItem.DoesNotExist:
        return Response({"error": "Tyre item not found."}, status=status.HTTP_404_NOT_FOUND)



