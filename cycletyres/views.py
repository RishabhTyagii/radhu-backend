import datetime
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import (
    CycleTyreItem, CycleTyreEntry, CycleTyreDailyManualEntry,
    BUCKET_CHOICES, COMPOUND_PERCENT,
)
from .serializers import (
    CycleTyreItemSerializer, CycleTyreEntrySerializer,
    CycleTyreDailyManualEntrySerializer,
)

def _recalculate_item_stocks():
    """Ensure CycleTyreItem stocks match Production - Sales + Adjustments entries."""
    for item in CycleTyreItem.objects.all():
        p1 = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='production').aggregate(t=Sum('first_grade'))['t'] or 0
        p2 = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='production').aggregate(t=Sum('second_grade'))['t'] or 0

        s1 = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='sale', bucket='stock').aggregate(t=Sum('quantity'))['t'] or 0
        s2 = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='sale', bucket='second_stock').aggregate(t=Sum('quantity'))['t'] or 0
        sr = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='sale', bucket='rfm_stock').aggregate(t=Sum('quantity'))['t'] or 0

        a1 = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='adjustment', bucket='stock').aggregate(t=Sum('quantity'))['t'] or 0
        a2 = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='adjustment', bucket='second_stock').aggregate(t=Sum('quantity'))['t'] or 0
        ar = CycleTyreEntry.objects.filter(tyre_item=item, entry_type='adjustment', bucket='rfm_stock').aggregate(t=Sum('quantity'))['t'] or 0

        item.stock = p1 - s1 + a1
        item.second_stock = p2 - s2 + a2
        item.rfm_stock = 0 - sr + ar
        item.save(update_fields=['stock', 'second_stock', 'rfm_stock'])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    # Recalculate live stocks from entries
    _recalculate_item_stocks()

    today = datetime.date.today()
    month_param = request.query_params.get("month", "all").strip()

    # Determine date filtering logic based on selected month
    prod_qs = CycleTyreEntry.objects.filter(entry_type="production")
    sale_qs = CycleTyreEntry.objects.filter(entry_type="sale")

    if month_param and month_param != "all":
        try:
            parts = month_param.split("-")
            year, month = int(parts[0]), int(parts[1])
            prod_qs = prod_qs.filter(date__year=year, date__month=month)
            sale_qs = sale_qs.filter(date__year=year, date__month=month)
        except (ValueError, IndexError):
            pass

    today_prod = CycleTyreEntry.objects.filter(date=today, entry_type="production").aggregate(total=Sum("quantity"))["total"] or 0
    today_sale = CycleTyreEntry.objects.filter(date=today, entry_type="sale").aggregate(total=Sum("quantity"))["total"] or 0

    month_prod = prod_qs.aggregate(total=Sum("quantity"))["total"] or 0
    month_sale = sale_qs.aggregate(total=Sum("quantity"))["total"] or 0

    active_items = CycleTyreItem.objects.filter(is_active=True)
    items_data = []

    total_stock = 0
    total_second_stock = 0
    total_rfm_stock = 0
    total_month_prod = 0
    total_month_sale = 0

    for item in active_items:
        i_prod_qs = CycleTyreEntry.objects.filter(tyre_item=item, entry_type="production")
        i_sale_qs = CycleTyreEntry.objects.filter(tyre_item=item, entry_type="sale")

        if month_param and month_param != "all":
            try:
                parts = month_param.split("-")
                year, month = int(parts[0]), int(parts[1])
                i_prod_qs = i_prod_qs.filter(date__year=year, date__month=month)
                i_sale_qs = i_sale_qs.filter(date__year=year, date__month=month)
            except (ValueError, IndexError):
                pass

        item_m_prod = i_prod_qs.aggregate(total=Sum("quantity"))["total"] or 0
        item_m_sale = i_sale_qs.aggregate(total=Sum("quantity"))["total"] or 0

        serialized = CycleTyreItemSerializer(item).data
        serialized["month_production"] = item_m_prod
        serialized["month_sale"] = item_m_sale
        items_data.append(serialized)

        total_stock += item.stock
        total_second_stock += item.second_stock
        total_rfm_stock += item.rfm_stock
        total_month_prod += item_m_prod
        total_month_sale += item_m_sale

    # Total combined stock = 1st Grade Stock + RFM Stock (excluding 2nd Grade Stock per user instruction)
    total_combined_stock = total_stock + total_rfm_stock

    # Available months for the dropdown selector
    available_months = [
        {"value": "all", "label": "All Months"},
        {"value": "2026-04", "label": "April 2026"},
        {"value": "2026-05", "label": "May 2026"},
        {"value": "2026-06", "label": "June 2026"},
        {"value": "2026-07", "label": "July 2026"},
        {"value": "2026-08", "label": "August 2026"},
    ]

    # Dynamic chart data for Production vs Sales comparison
    chart_months = [
        ("April 2026", 2026, 4),
        ("May 2026", 2026, 5),
        ("June 2026", 2026, 6),
        ("July 2026", 2026, 7),
        ("August 2026", 2026, 8),
    ]
    chart_data = []
    for label, y, m in chart_months:
        p_val = CycleTyreEntry.objects.filter(entry_type="production", date__year=y, date__month=m).aggregate(t=Sum("quantity"))["t"] or 0
        s_val = CycleTyreEntry.objects.filter(entry_type="sale", date__year=y, date__month=m).aggregate(t=Sum("quantity"))["t"] or 0
        chart_data.append({"month": label, "key": f"{y}-{m:02d}", "production": p_val, "sale": s_val})

    return Response({
        "selected_month": month_param,
        "available_months": available_months,
        "chart_data": chart_data,
        "stats": {
            "today_production": today_prod,
            "today_sale": today_sale,
            "month_production": month_prod,
            "month_sale": month_sale,
        },
        "totals": {
            "total_stock": total_stock,
            "total_second_stock": total_second_stock,
            "total_rfm_stock": total_rfm_stock,
            "total_combined_stock": total_combined_stock,
            "total_month_production": total_month_prod,
            "total_month_sale": total_month_sale,
        },
        "items": items_data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_item(request):
    serializer = CycleTyreItemSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def add_production(request):
    if request.method == "GET":
        items = CycleTyreItem.objects.filter(is_active=True)
        recent_entries = CycleTyreEntry.objects.filter(entry_type="production")[:15]
        return Response({
            "items": CycleTyreItemSerializer(items, many=True).data,
            "recent_entries": CycleTyreEntrySerializer(recent_entries, many=True).data,
        })

    tyre_item_id = request.data.get("tyre_item")
    all_curing = int(request.data.get("all_curing") or 0)
    second_grade = int(request.data.get("second_grade") or 0)
    rejected_grade = int(request.data.get("rejected_grade") or 0)
    date_val = request.data.get("date", str(datetime.date.today()))
    remark = request.data.get("remark", "").strip()

    if not tyre_item_id or all_curing <= 0:
        return Response({"error": "tyre_item and all_curing (> 0) are required."}, status=status.HTTP_400_BAD_REQUEST)

    first_grade = all_curing - (second_grade + rejected_grade)
    if first_grade < 0:
        return Response({
            "error": f"Invalid entry: 2nd Grade ({second_grade}) + Rejected ({rejected_grade}) is greater than All Curing ({all_curing})!"
        }, status=status.HTTP_400_BAD_REQUEST)

    item = get_object_or_404(CycleTyreItem, pk=tyre_item_id)

    with transaction.atomic():
        item.stock += first_grade
        item.second_stock += second_grade
        item.save(update_fields=["stock", "second_stock"])

        entry = CycleTyreEntry.objects.create(
            tyre_item=item,
            entry_type="production",
            bucket="stock",
            quantity=first_grade,
            all_curing=all_curing,
            first_grade=first_grade,
            second_grade=second_grade,
            rejected_grade=rejected_grade,
            date=date_val,
            remark=remark,
            user=request.user if request.user.is_authenticated else None,
        )

    return Response(CycleTyreEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def second_grade_stock(request):
    items = CycleTyreItem.objects.filter(is_active=True)
    total_second_stock = sum(item.second_stock for item in items)

    # 2nd Grade Production Logs
    second_grade_entries = CycleTyreEntry.objects.filter(
        entry_type="production", second_grade__gt=0
    ).select_related("tyre_item", "user")[:25]

    # 2nd Grade Sales Logs (B Grade Sales)
    second_grade_sales = CycleTyreEntry.objects.filter(
        entry_type="sale", bucket="second_stock"
    ).select_related("tyre_item", "user")

    total_second_sales = second_grade_sales.aggregate(total=Sum("quantity"))["total"] or 0

    return Response({
        "items": CycleTyreItemSerializer(items, many=True).data,
        "total_second_stock": total_second_stock,
        "total_second_sales": total_second_sales,
        "second_grade_entries": CycleTyreEntrySerializer(second_grade_entries, many=True).data,
        "second_grade_sales": CycleTyreEntrySerializer(second_grade_sales[:25], many=True).data,
    })



@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def add_sale(request):
    if request.method == "GET":
        items = CycleTyreItem.objects.filter(is_active=True)
        recent_entries = CycleTyreEntry.objects.filter(entry_type="sale")[:15]
        return Response({
            "items": CycleTyreItemSerializer(items, many=True).data,
            "recent_entries": CycleTyreEntrySerializer(recent_entries, many=True).data,
        })

    tyre_item_id = request.data.get("tyre_item")
    quantity = int(request.data.get("quantity") or 0)
    bucket = request.data.get("bucket", "stock")
    date_val = request.data.get("date", str(datetime.date.today()))
    bill_number = request.data.get("bill_number", "").strip()
    remark = request.data.get("remark", "").strip()

    if not tyre_item_id or quantity <= 0:
        return Response({"error": "tyre_item and quantity (> 0) are required."}, status=status.HTTP_400_BAD_REQUEST)

    if bill_number and CycleTyreEntry.objects.filter(bill_number__iexact=bill_number, entry_type="sale").exists():
        return Response({"error": f"Bill number '{bill_number}' already exists in sale entries."}, status=status.HTTP_400_BAD_REQUEST)

    item = get_object_or_404(CycleTyreItem, pk=tyre_item_id)
    available_stock = getattr(item, bucket, 0)
    if quantity > available_stock:
        bucket_name = dict(BUCKET_CHOICES).get(bucket, bucket)
        return Response({"error": f"Insufficient stock in '{bucket_name}'. Available: {available_stock}, Requested: {quantity}."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        setattr(item, bucket, available_stock - quantity)
        item.save(update_fields=[bucket])

        entry = CycleTyreEntry.objects.create(
            tyre_item=item,
            entry_type="sale",
            bucket=bucket,
            quantity=quantity,
            date=date_val,
            bill_number=bill_number,
            remark=remark,
            user=request.user if request.user.is_authenticated else None,
        )

    return Response(CycleTyreEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def add_adjustment(request):
    if request.method == "GET":
        items = CycleTyreItem.objects.filter(is_active=True)
        recent_entries = CycleTyreEntry.objects.filter(entry_type="adjustment")[:15]
        return Response({
            "items": CycleTyreItemSerializer(items, many=True).data,
            "recent_entries": CycleTyreEntrySerializer(recent_entries, many=True).data,
        })

    tyre_item_id = request.data.get("tyre_item")
    quantity = int(request.data.get("quantity") or 0)
    bucket = request.data.get("bucket", "stock")
    date_val = request.data.get("date", str(datetime.date.today()))
    remark = request.data.get("remark", "").strip()

    if not tyre_item_id or quantity == 0:
        return Response({"error": "tyre_item and quantity (!= 0) are required."}, status=status.HTTP_400_BAD_REQUEST)

    item = get_object_or_404(CycleTyreItem, pk=tyre_item_id)
    curr_stock = getattr(item, bucket, 0)

    if quantity < 0 and (curr_stock + quantity < 0):
        return Response({"error": f"Adjustment results in negative stock in '{bucket}'. Current: {curr_stock}, Adjustment: {quantity}."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        setattr(item, bucket, curr_stock + quantity)
        item.save(update_fields=[bucket])

        entry = CycleTyreEntry.objects.create(
            tyre_item=item,
            entry_type="adjustment",
            bucket=bucket,
            quantity=quantity,
            date=date_val,
            remark=remark,
            user=request.user if request.user.is_authenticated else None,
        )

    return Response(CycleTyreEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def entries_log(request):
    qs = CycleTyreEntry.objects.select_related("tyre_item", "user").all()

    date_param = request.query_params.get("date")
    month_param = request.query_params.get("month")
    entry_type = request.query_params.get("entry_type") or request.query_params.get("type")

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

    return Response(CycleTyreEntrySerializer(qs[:500], many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_report(request):
    today = datetime.date.today()
    year = int(request.query_params.get("year", today.year))
    month = int(request.query_params.get("month", today.month))

    items = CycleTyreItem.objects.filter(is_active=True)
    report_items = []
    tot_prod, tot_sale, tot_stock, tot_second, tot_rfm = 0, 0, 0, 0, 0

    for item in items:
        prod_qty = CycleTyreEntry.objects.filter(
            tyre_item=item, entry_type="production", date__year=year, date__month=month
        ).aggregate(total=Sum("quantity"))["total"] or 0

        sale_qty = CycleTyreEntry.objects.filter(
            tyre_item=item, entry_type="sale", date__year=year, date__month=month
        ).aggregate(total=Sum("quantity"))["total"] or 0

        serialized = CycleTyreItemSerializer(item).data
        serialized["monthly_production"] = prod_qty
        serialized["monthly_sale"] = sale_qty
        report_items.append(serialized)

        tot_prod += prod_qty
        tot_sale += sale_qty
        tot_stock += item.stock
        tot_second += item.second_stock
        tot_rfm += item.rfm_stock

    return Response({
        "year": year,
        "month": month,
        "items": report_items,
        "totals": {
            "total_monthly_production": tot_prod,
            "total_monthly_sale": tot_sale,
            "total_stock": tot_stock,
            "total_second_stock": tot_second,
            "total_rfm_stock": tot_rfm,
            "total_combined_stock": tot_stock + tot_second + tot_rfm,
        }
    })


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def daily_summary(request):
    today = datetime.date.today()

    if request.method == "POST":
        date_val = request.data.get("date") or today
        def to_dec(v):
            try: return Decimal(str(v)) if v else Decimal("0.00")
            except: return Decimal("0.00")

        manual, created = CycleTyreDailyManualEntry.objects.update_or_create(
            date=date_val,
            defaults={
                "parchi_kg": to_dec(request.data.get("parchi_kg")),
                "mixing_actual_compound": to_dec(request.data.get("mixing_actual_compound")),
                "chakka": to_dec(request.data.get("chakka")),
                "calander_bias_cutt": to_dec(request.data.get("calander_bias_cutt")),
                "packing_wastage": to_dec(request.data.get("packing_wastage")),
                "tar": to_dec(request.data.get("tar")),
            }
        )
        return Response(CycleTyreDailyManualEntrySerializer(manual).data)

    start_date_str = request.query_params.get("start_date") or request.query_params.get("from_date")
    end_date_str = request.query_params.get("end_date") or request.query_params.get("to_date")

    try: start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else today.replace(day=1)
    except: start_date = today.replace(day=1)
    try: end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else today
    except: end_date = today

    prod_entries = CycleTyreEntry.objects.filter(
        entry_type="production", date__gte=start_date, date__lte=end_date
    ).select_related("tyre_item")

    by_date = {}
    for e in prod_entries:
        d = by_date.setdefault(e.date, {"production_pcs": 0, "packing_pcs": 0, "theoretical_kg": Decimal("0.00")})
        curing_qty = e.all_curing if e.all_curing > 0 else e.quantity
        first_grade_qty = e.first_grade if e.first_grade > 0 else e.quantity
        weight = e.tyre_item.weight or Decimal("0.00")

        d["production_pcs"] += curing_qty
        d["packing_pcs"] += first_grade_qty
        d["theoretical_kg"] += Decimal(str(curing_qty)) * weight

    manual_entries = {m.date: m for m in CycleTyreDailyManualEntry.objects.filter(date__gte=start_date, date__lte=end_date)}
    all_dates = sorted(list(set(by_date.keys()).union(set(manual_entries.keys()))), reverse=True)

    rows = []
    tot_prod_pcs, tot_pack_pcs = 0, 0
    tot_theo_kg, tot_parchi_kg, tot_diff = Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
    tot_theo_comp, tot_mixing_act, tot_var = Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
    tot_chakka, tot_calander, tot_pack_w, tot_tar = Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")

    for d in all_dates:
        stats = by_date.get(d, {"production_pcs": 0, "packing_pcs": 0, "theoretical_kg": Decimal("0.00")})
        manual = manual_entries.get(d)

        parchi_kg = manual.parchi_kg if manual else Decimal("0.00")
        mixing_actual = manual.mixing_actual_compound if manual else Decimal("0.00")
        chakka = manual.chakka if manual else Decimal("0.00")
        calander = manual.calander_bias_cutt if manual else Decimal("0.00")
        packing_w = manual.packing_wastage if manual else Decimal("0.00")
        tar = manual.tar if manual else Decimal("0.00")

        theoretical_kg = stats["theoretical_kg"]
        difference = parchi_kg - theoretical_kg
        theoretical_total_compound = theoretical_kg * COMPOUND_PERCENT
        variance = mixing_actual - theoretical_total_compound

        rows.append({
            "date": str(d),
            "production_pcs": stats["production_pcs"],
            "packing_pcs": stats["packing_pcs"],
            "theoretical_kg": str(round(theoretical_kg, 2)),
            "parchi_kg": str(parchi_kg),
            "difference": str(round(difference, 2)),
            "theoretical_total_compound": str(round(theoretical_total_compound, 2)),
            "mixing_actual_compound": str(mixing_actual),
            "variance": str(round(variance, 2)),
            "chakka": str(chakka),
            "calander_bias_cutt": str(calander),
            "packing_wastage": str(packing_w),
            "tar": str(tar),
        })

        tot_prod_pcs += stats["production_pcs"]
        tot_pack_pcs += stats["packing_pcs"]
        tot_theo_kg += theoretical_kg
        tot_parchi_kg += parchi_kg
        tot_diff += difference
        tot_theo_comp += theoretical_total_compound
        tot_mixing_act += mixing_actual
        tot_var += variance
        tot_chakka += chakka
        tot_calander += calander
        tot_pack_w += packing_w
        tot_tar += tar

    return Response({
        "summary": rows,
        "totals": {
            "production_pcs": tot_prod_pcs,
            "packing_pcs": tot_pack_pcs,
            "theoretical_kg": str(round(tot_theo_kg, 2)),
            "parchi_kg": str(round(tot_parchi_kg, 2)),
            "difference": str(round(tot_diff, 2)),
            "theoretical_total_compound": str(round(tot_theo_comp, 2)),
            "mixing_actual_compound": str(round(tot_mixing_act, 2)),
            "variance": str(round(tot_var, 2)),
            "chakka": str(round(tot_chakka, 2)),
            "calander_bias_cutt": str(round(tot_calander, 2)),
            "packing_wastage": str(round(tot_pack_w, 2)),
            "tar": str(round(tot_tar, 2)),
        },
        "start_date": str(start_date),
        "end_date": str(end_date),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_production_excel(request):
    import openpyxl

    file_obj = request.FILES.get("file") or request.FILES.get("excel_file")
    if not file_obj:
        return Response({"error": "No file uploaded. Please select an Excel (.xlsx) file."}, status=status.HTTP_400_BAD_REQUEST)

    clear_existing = str(request.data.get("clear_existing", "true")).lower() in ["true", "1", "yes"]

    # Accept user-selected date — all imported entries will use this date
    import_date_str = request.data.get("import_date") or request.data.get("date")
    user_date = None
    if import_date_str:
        try:
            user_date = datetime.datetime.strptime(str(import_date_str).strip(), "%Y-%m-%d").date()
        except ValueError:
            pass

    # Accept which month columns to import (optional, default: all)
    import_month = request.data.get("import_month", "all")  # 'all', 'april', 'may', 'june', 'july'

    try:
        wb = openpyxl.load_workbook(file_obj, data_only=True)
        ws = wb.active
    except Exception as e:
        return Response({"error": f"Failed to open Excel file: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    # Default month dates — used only when user_date is not provided
    MONTHS = {
        'april': datetime.date(2026, 4, 15),
        'may': datetime.date(2026, 5, 15),
        'june': datetime.date(2026, 6, 15),
        'july': datetime.date(2026, 7, 15),
    }

    MONTH_COLS = {
        'april': {'black': 5, 'second': 6, 'rejected': 7, 'all_curing': 8},
        'may': {'black': 9, 'second': 10, 'rejected': 11, 'all_curing': 12},
        'june': {'black': 13, 'second': 14, 'rejected': 15, 'all_curing': 16},
        'july': {'black': 17, 'second': 18, 'rejected': 19, 'all_curing': 20},
    }

    # If user selected a specific month column to import
    if import_month and import_month != 'all' and import_month in MONTH_COLS:
        active_months = [import_month]
    else:
        active_months = ['april', 'may', 'june', 'july']

    def safe_int(v):
        if v is None: return 0
        try: return int(v)
        except: return 0

    def find_item_exact(size, mat_raw, brand, p_num):
        size = (size or '').strip()
        mat_raw = (mat_raw or '').strip()
        brand = (brand or '').strip()
        if not size or not mat_raw: return None

        if p_num and p_num > 0:
            mat_with_ply = f'{mat_raw} ({p_num} Ply)'
            box_with_ply = f'{p_num} ply'
            it = CycleTyreItem.objects.filter(size__iexact=size, material__iexact=mat_with_ply, brand__iexact=brand).first()
            if it: return it
            it = CycleTyreItem.objects.filter(size__iexact=size, box_type__iexact=box_with_ply, brand__iexact=brand).first()
            if it: return it

        it = CycleTyreItem.objects.filter(size__iexact=size, material__iexact=mat_raw, brand__iexact=brand).first()
        if it: return it
        return CycleTyreItem.objects.filter(size__iexact=size, material__iexact=mat_raw).first()

    data_rows = []
    for r in range(5, min(ws.max_row + 1, 75)):
        vals = [ws.cell(row=r, column=c).value for c in range(1, 22)]
        p_num = safe_int(vals[0]) if vals[0] is not None else None
        size = vals[2]
        mat = vals[3]
        brand = vals[4]
        if not size or not mat: continue

        row_data = {
            'row_num': r,
            'ply_num': p_num,
            'size': str(size).strip(),
            'material': str(mat).strip(),
            'brand': str(brand).strip() if brand else '',
            'months': {}
        }
        for month_name, cols in MONTH_COLS.items():
            black = safe_int(vals[cols['black']])
            second = safe_int(vals[cols['second']])
            rejected = safe_int(vals[cols['rejected']])
            all_curing = safe_int(vals[cols['all_curing']])
            row_data['months'][month_name] = {
                'all_curing': all_curing,
                'first_grade': black,
                'second_grade': second,
                'rejected_grade': rejected,
            }
        data_rows.append(row_data)

    if not data_rows:
        return Response({"error": "No valid production data found in Excel sheet."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        if clear_existing:
            CycleTyreEntry.objects.filter(entry_type="production").delete()
            CycleTyreDailyManualEntry.objects.all().delete()
            CycleTyreItem.objects.all().update(stock=0, second_stock=0, rfm_stock=0)

        created_count = 0
        matched_items = set()
        dates_used = set()

        for row_data in data_rows:
            item = find_item_exact(
                row_data['size'], row_data['material'], row_data['brand'], row_data['ply_num']
            )
            if not item: continue
            matched_items.add(item.id)

            for month_name in active_months:
                m = row_data['months'][month_name]
                all_curing = m['all_curing']
                if all_curing <= 0: continue

                first_grade = m['first_grade']
                second_grade = m['second_grade']
                rejected_grade = m['rejected_grade']

                total_breakdown = first_grade + second_grade + rejected_grade
                if total_breakdown != all_curing:
                    first_grade = all_curing - second_grade - rejected_grade
                    if first_grade < 0: first_grade = 0

                # Use user-selected date if provided, otherwise fall back to month default
                if user_date:
                    date_val = user_date
                else:
                    date_val = MONTHS[month_name]

                dates_used.add(str(date_val))

                CycleTyreEntry.objects.create(
                    tyre_item=item,
                    entry_type='production',
                    bucket='stock',
                    quantity=first_grade,
                    all_curing=all_curing,
                    first_grade=first_grade,
                    second_grade=second_grade,
                    rejected_grade=rejected_grade,
                    date=date_val,
                    remark=f'{month_name.title()} Excel import ({date_val})',
                    user=request.user if request.user.is_authenticated else None,
                )

                item.stock += first_grade
                item.second_stock += second_grade
                created_count += 1

            item.save(update_fields=['stock', 'second_stock'])

        # Summary by actual dates used
        month_summary = []
        for d_str in sorted(dates_used):
            d = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
            entries = CycleTyreEntry.objects.filter(date=d, entry_type='production')
            month_summary.append({
                "month": d.strftime("%B"),
                "date": d_str,
                "count": entries.count(),
                "curing": sum(e.all_curing for e in entries),
                "first_grade": sum(e.first_grade for e in entries),
                "second_grade": sum(e.second_grade for e in entries),
                "rejected": sum(e.rejected_grade for e in entries),
            })

        items = CycleTyreItem.objects.filter(is_active=True)
        tot_stock = sum(i.stock for i in items)
        tot_second = sum(i.second_stock for i in items)
        tot_rfm = sum(i.rfm_stock for i in items)

    return Response({
        "message": f"Successfully imported {created_count} production entries from Excel!",
        "created_entries": created_count,
        "matched_items": len(matched_items),
        "total_stock": tot_stock,
        "total_second_stock": tot_second,
        "total_rfm_stock": tot_rfm,
        "total_combined": tot_stock + tot_second + tot_rfm,
        "month_summary": month_summary,
        "dates_used": sorted(list(dates_used)),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def production_sheet(request):
    date_param = request.query_params.get("date")
    month_param = request.query_params.get("month")

    today = datetime.date.today()

    if date_param:
        try:
            target_date = datetime.datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            target_date = today
        entries = CycleTyreEntry.objects.filter(entry_type="production", date=target_date).select_related("tyre_item")
    elif month_param:
        try:
            parts = month_param.split("-")
            year, month = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            year, month = today.year, today.month
        entries = CycleTyreEntry.objects.filter(entry_type="production", date__year=year, date__month=month).select_related("tyre_item")
    else:
        # Default to current month instead of showing ALL entries
        entries = CycleTyreEntry.objects.filter(entry_type="production", date__year=today.year, date__month=today.month).select_related("tyre_item")

    item_map = {}
    tot_curing, tot_first, tot_second, tot_rejected = 0, 0, 0, 0

    for e in entries:
        tid = e.tyre_item.id
        if tid not in item_map:
            item_map[tid] = {
                "id": tid,
                "tyre_name": f"{e.tyre_item.size} {e.tyre_item.box_type} {e.tyre_item.material} {e.tyre_item.brand}".strip(),
                "size": e.tyre_item.size,
                "box_type": e.tyre_item.box_type,
                "material": e.tyre_item.material,
                "brand": e.tyre_item.brand,
                "all_curing": 0,
                "first_grade": 0,
                "second_grade": 0,
                "rejected_grade": 0,
            }
        
        curing_qty = e.all_curing if e.all_curing > 0 else e.quantity
        first_qty = e.first_grade if e.first_grade > 0 else e.quantity
        second_qty = e.second_grade
        rejected_qty = e.rejected_grade

        item_map[tid]["all_curing"] += curing_qty
        item_map[tid]["first_grade"] += first_qty
        item_map[tid]["second_grade"] += second_qty
        item_map[tid]["rejected_grade"] += rejected_qty

        tot_curing += curing_qty
        tot_first += first_qty
        tot_second += second_qty
        tot_rejected += rejected_qty

    rows = list(item_map.values())
    rows.sort(key=lambda x: (x["size"], x["box_type"], x["material"], x["brand"]))

    return Response({
        "data": rows,
        "totals": {
            "all_curing": tot_curing,
            "first_grade": tot_first,
            "second_grade": tot_second,
            "rejected_grade": tot_rejected,
        },
        "count": len(rows),
        "date": date_param or str(today),
        "month": month_param or today.strftime("%Y-%m"),
    })












