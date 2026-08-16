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

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    q = request.GET.get("q", "")
    items = TyreItem.objects.filter(is_active=True)
    if q:
        items = items.filter(Q(tyre__icontains=q) | Q(pattern__icontains=q) | Q(type__icontains=q))

    today = datetime.date.today()
    month_start = today.replace(day=1)

    today_production = DailyEntry.objects.filter(entry_type="production", date=today).aggregate(Sum("quantity"))['quantity__sum'] or 0
    today_dispatch = DailyEntry.objects.filter(entry_type="dispatch", date=today).aggregate(Sum("quantity"))['quantity__sum'] or 0
    
    grand_total = 0
    total_stock_col = 0
    total_repair = 0
    total_rfm = 0
    total_old = 0
    total_hold = 0
    total_curing = 0
    total_despatch = 0

    response_items = []
    for item in items:
        month_curing = DailyEntry.objects.filter(tyre_item=item, entry_type="production", date__gte=month_start, date__lte=today).aggregate(Sum("all_curing"))['all_curing__sum'] or 0
        month_despatch = DailyEntry.objects.filter(tyre_item=item, entry_type="dispatch", date__gte=month_start, date__lte=today).aggregate(Sum("quantity"))['quantity__sum'] or 0
        
        serialized = TyreItemSerializer(item).data
        serialized["month_curing"] = month_curing
        serialized["month_despatch"] = month_despatch
        response_items.append(serialized)

        grand_total += item.total_stock
        total_stock_col += item.stock
        total_repair += item.repair_tyre_stock
        total_rfm += item.rfm_ok_tyre
        total_old += item.old_tyres_2025
        total_hold += item.on_hold_export
        total_curing += month_curing
        total_despatch += month_despatch

    month_production = total_curing
    month_dispatch = total_despatch

    return Response({
        "items": response_items,
        "today_production": today_production,
        "today_dispatch": today_dispatch,
        "month_production": month_production,
        "month_dispatch": month_dispatch,
        "totals": {
            "grand_total": grand_total,
            "stock": total_stock_col,
            "repair": total_repair,
            "rfm": total_rfm,
            "old": total_old,
            "hold": total_hold,
            "curing": total_curing,
            "despatch": total_despatch,
        }
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
        item.save(update_fields=["stock"])

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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def production_sheet(request):
    date_param = request.GET.get("date")
    month_param = request.GET.get("month")
    
    if date_param:
        entries = DailyEntry.objects.filter(entry_type="production", date=date_param).select_related("tyre_item")
    elif month_param:
        try:
            year, month = month_param.split("-")
            entries = DailyEntry.objects.filter(entry_type="production", date__year=year, date__month=month).select_related("tyre_item")
        except:
            today = datetime.date.today()
            entries = DailyEntry.objects.filter(entry_type="production", date__year=today.year, date__month=today.month).select_related("tyre_item")
    else:
        today = datetime.date.today()
        entries = DailyEntry.objects.filter(entry_type="production", date__year=today.year, date__month=today.month).select_related("tyre_item")

    # Assuming no pagination logic for now as it's not strictly required in standard response size and complexity might break exactness without DRF paginator setup. We will return all matching.
    
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
            
            labels.append(str(entry.tyre_item))
            curing_data.append(entry.all_curing)
            packing_data.append(entry.quantity)
            repair_data.append(entry.repair)
            second_data.append(entry.second_grade)
            third_data.append(entry.third_grade)
            lose_data.append(entry.lose_tyre)
            
    else:
        # aggregate by tyre item
        tyre_aggregates = {}
        for entry in entries:
            tid = entry.tyre_item.id
            if tid not in tyre_aggregates:
                tyre_aggregates[tid] = {
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
            
        for tid, agg in tyre_aggregates.items():
            data_list.append(agg)
            for k in totals.keys():
                totals[k] += agg[k]
                
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
def production_sheet_export(request):
    # Simpler version leveraging the same logic, then exporting to openpyxl
    response = production_sheet(request._request)
    if response.status_code != 200:
        return response
        
    data = response.data["data"]
    totals = response.data["totals"]
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Production Sheet"
    
    headers = ["Tyre Item", "All Curing", "Production Tyre", "Repair", "2nd Grade", "3rd Grade", "Lose Tyre", "Packing", "RFM Adjustment"]
    ws.append(headers)
    
    for row in data:
        ws.append([
            row["tyre_name"], row["all_curing"], row["production_tyre"], row["repair"],
            row["second_grade"], row["third_grade"], row["lose_tyre"], row["packing"], row["rfm_adjustment"]
        ])
        
    ws.append([
        "TOTAL", totals["all_curing"], totals["production_tyre"], totals["repair"],
        totals["second_grade"], totals["third_grade"], totals["lose_tyre"], totals["packing"], totals["rfm_adjustment"]
    ])
    
    http_response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    http_response["Content-Disposition"] = 'attachment; filename="production_sheet.xlsx"'
    wb.save(http_response)
    return http_response

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def daily_summary(request):
    if request.method == "POST":
        data = request.data
        entry_date = data.get("entry_date")
        if not entry_date:
            return Response({"error": "entry_date is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        obj, created = DailyProductionManualEntry.objects.update_or_create(
            date=entry_date,
            defaults={
                "parchi_kg": data.get("parchi_kg", 0),
                "mixing_actual_compound": data.get("mixing_actual_compound", 0),
                "wastage": data.get("wastage", 0)
            }
        )
        return Response({"message": "Saved successfully", "date": entry_date})

    # GET method
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    
    today = datetime.date.today()
    if not from_date:
        from_date = today.replace(day=1)
    if not to_date:
        to_date = today
        
    entries = DailyEntry.objects.filter(entry_type="production", date__gte=from_date, date__lte=to_date).select_related("tyre_item")
    
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
    
    results = []
    COMPOUND_PERCENT = 0.877
    
    for d, data in dates_data.items():
        me = manual_dict.get(d)
        parchi_kg = float(me.parchi_kg) if me else 0.0
        mixing_actual = float(me.mixing_actual_compound) if me else 0.0
        wastage = float(me.wastage) if me else 0.0
        
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
        
    results.sort(key=lambda x: x["date"], reverse=True)
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


