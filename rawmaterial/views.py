import datetime
from decimal import Decimal
from django.db.models import Sum
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import MixingEntry


def serialize_entry(entry):
    date_val = entry.date
    if hasattr(date_val, "strftime"):
        date_str = date_val.strftime("%Y-%m-%d")
    else:
        date_str = str(date_val)

    return {
        "id": entry.id,
        "date": date_str,
        "compound": {
            "ct": float(entry.compound_ct),
            "cc": float(entry.compound_cc),
            "crt": float(entry.compound_crt),
            "ncc": float(entry.compound_ncc),
            "nct": float(entry.compound_nct),
            "nrt": float(entry.compound_nrt),
            "tar": float(entry.compound_tar),
            "cycle_tube": float(entry.compound_cycle_tube),
            "moulding_tube": float(entry.compound_moulding_tube),
            "auto_tyre": float(entry.compound_auto_tyre),
            "lcv_tyre": float(entry.compound_lcv_tyre),
            "auto_calender": float(entry.compound_auto_calender),
            "tractor": float(entry.compound_tractor),
            "total": float(entry.compound_total),
        },
        "rubber": {
            "ct": float(entry.rubber_ct),
            "cc": float(entry.rubber_cc),
            "crt": float(entry.rubber_crt),
            "ncc": float(entry.rubber_ncc),
            "nct": float(entry.rubber_nct),
            "nrt": float(entry.rubber_nrt),
            "tar": float(entry.rubber_tar),
            "cycle_tube": float(entry.rubber_cycle_tube),
            "moulding_tube": float(entry.rubber_moulding_tube),
            "auto_tyre": float(entry.rubber_auto_tyre),
            "lcv_tyre": float(entry.rubber_lcv_tyre),
            "auto_calender": float(entry.rubber_auto_calender),
            "tractor": float(entry.rubber_tractor),
            "total": float(entry.rubber_total),
        },
        "reconciliation": {
            "rubber_bdls": float(entry.rubber_bdls),
            "rubber_kgs": float(entry.rubber_kgs),
            "diff": float(entry.diff),
        },
        "notes": entry.notes or "",
    }


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def mixing_sheet_view(request):
    """
    GET: Returns mixing entries for month/year or date range with totals.
    POST: Creates or updates an entry for a specific date.
    """
    if request.method == "GET":
        month = request.GET.get("month")
        year = request.GET.get("year")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        queryset = MixingEntry.objects.all()

        if start_date and end_date:
            queryset = queryset.filter(date__range=[start_date, end_date])
        elif month and year:
            queryset = queryset.filter(date__year=int(year), date__month=int(month))
        else:
            # Default to the latest available entry's month and year
            latest_entry = MixingEntry.objects.order_by("-date").first()
            if latest_entry:
                active_year = latest_entry.date.year
                active_month = latest_entry.date.month
            else:
                today = datetime.date.today()
                active_year = today.year
                active_month = today.month
            queryset = queryset.filter(date__year=active_year, date__month=active_month)

        entries = list(queryset.order_by("date"))
        data = [serialize_entry(e) for e in entries]

        # Calculate monthly totals
        monthly_totals = {
            "compound_total": sum(float(e.compound_total) for e in entries),
            "rubber_total": sum(float(e.rubber_total) for e in entries),
            "rubber_bdls": sum(float(e.rubber_bdls) for e in entries),
            "rubber_kgs": sum(float(e.rubber_kgs) for e in entries),
            "diff": sum(float(e.diff) for e in entries),
            "compound_breakdown": {
                "ct": sum(float(e.compound_ct) for e in entries),
                "cc": sum(float(e.compound_cc) for e in entries),
                "crt": sum(float(e.compound_crt) for e in entries),
                "ncc": sum(float(e.compound_ncc) for e in entries),
                "nct": sum(float(e.compound_nct) for e in entries),
                "nrt": sum(float(e.compound_nrt) for e in entries),
                "tar": sum(float(e.compound_tar) for e in entries),
                "cycle_tube": sum(float(e.compound_cycle_tube) for e in entries),
                "moulding_tube": sum(float(e.compound_moulding_tube) for e in entries),
                "auto_tyre": sum(float(e.compound_auto_tyre) for e in entries),
                "lcv_tyre": sum(float(e.compound_lcv_tyre) for e in entries),
                "auto_calender": sum(float(e.compound_auto_calender) for e in entries),
                "tractor": sum(float(e.compound_tractor) for e in entries),
            },
            "rubber_breakdown": {
                "ct": sum(float(e.rubber_ct) for e in entries),
                "cc": sum(float(e.rubber_cc) for e in entries),
                "crt": sum(float(e.rubber_crt) for e in entries),
                "ncc": sum(float(e.rubber_ncc) for e in entries),
                "nct": sum(float(e.rubber_nct) for e in entries),
                "nrt": sum(float(e.rubber_nrt) for e in entries),
                "tar": sum(float(e.rubber_tar) for e in entries),
                "cycle_tube": sum(float(e.rubber_cycle_tube) for e in entries),
                "moulding_tube": sum(float(e.rubber_moulding_tube) for e in entries),
                "auto_tyre": sum(float(e.rubber_auto_tyre) for e in entries),
                "lcv_tyre": sum(float(e.rubber_lcv_tyre) for e in entries),
                "auto_calender": sum(float(e.rubber_auto_calender) for e in entries),
                "tractor": sum(float(e.rubber_tractor) for e in entries),
            },
        }

        return Response({
            "status": "success",
            "active_month": str(active_month if not (month and year) else month),
            "active_year": str(active_year if not (month and year) else year),
            "count": len(data),
            "entries": data,
            "totals": monthly_totals,
        })

    elif request.method == "POST":
        payload = request.data
        date_str = payload.get("date")
        if not date_str:
            return Response({"error": "Date is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure parsed date object
        if isinstance(date_str, str):
            try:
                parsed_date = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            except ValueError:
                return Response({"error": "Invalid date format, expected YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            parsed_date = date_str

        compound = payload.get("compound", {})
        rubber = payload.get("rubber", {})
        reconciliation = payload.get("reconciliation", {})

        entry, created = MixingEntry.objects.get_or_create(date=parsed_date)

        # Compound fields
        entry.compound_ct = Decimal(str(compound.get("ct", 0) or 0))
        entry.compound_cc = Decimal(str(compound.get("cc", 0) or 0))
        entry.compound_crt = Decimal(str(compound.get("crt", 0) or 0))
        entry.compound_ncc = Decimal(str(compound.get("ncc", 0) or 0))
        entry.compound_nct = Decimal(str(compound.get("nct", 0) or 0))
        entry.compound_nrt = Decimal(str(compound.get("nrt", 0) or 0))
        entry.compound_tar = Decimal(str(compound.get("tar", 0) or 0))
        entry.compound_cycle_tube = Decimal(str(compound.get("cycle_tube", 0) or 0))
        entry.compound_moulding_tube = Decimal(str(compound.get("moulding_tube", 0) or 0))
        entry.compound_auto_tyre = Decimal(str(compound.get("auto_tyre", 0) or 0))
        entry.compound_lcv_tyre = Decimal(str(compound.get("lcv_tyre", 0) or 0))
        entry.compound_auto_calender = Decimal(str(compound.get("auto_calender", 0) or 0))
        entry.compound_tractor = Decimal(str(compound.get("tractor", 0) or 0))

        # Rubber fields
        entry.rubber_ct = Decimal(str(rubber.get("ct", 0) or 0))
        entry.rubber_cc = Decimal(str(rubber.get("cc", 0) or 0))
        entry.rubber_crt = Decimal(str(rubber.get("crt", 0) or 0))
        entry.rubber_ncc = Decimal(str(rubber.get("ncc", 0) or 0))
        entry.rubber_nct = Decimal(str(rubber.get("nct", 0) or 0))
        entry.rubber_nrt = Decimal(str(rubber.get("nrt", 0) or 0))
        entry.rubber_tar = Decimal(str(rubber.get("tar", 0) or 0))
        entry.rubber_cycle_tube = Decimal(str(rubber.get("cycle_tube", 0) or 0))
        entry.rubber_moulding_tube = Decimal(str(rubber.get("moulding_tube", 0) or 0))
        entry.rubber_auto_tyre = Decimal(str(rubber.get("auto_tyre", 0) or 0))
        entry.rubber_lcv_tyre = Decimal(str(rubber.get("lcv_tyre", 0) or 0))
        entry.rubber_auto_calender = Decimal(str(rubber.get("auto_calender", 0) or 0))
        entry.rubber_tractor = Decimal(str(rubber.get("tractor", 0) or 0))

        # Reconciliation
        entry.rubber_bdls = Decimal(str(reconciliation.get("rubber_bdls", 0) or 0))
        entry.notes = payload.get("notes", "")

        entry.save()

        # Automatically sync to Cycle Tyre, Cycle Tube, and Auto Tyre Daily Summary sheets
        sync_mixing_to_summaries(entry)

        return Response({
            "status": "success",
            "message": "Entry created successfully" if created else "Entry updated successfully",
            "entry": serialize_entry(entry),
        })


def sync_mixing_to_summaries(entry):
    """
    Syncs the mixing sheet compound values to the 3 daily summary sheets:
    1. Cycle Tyre Summary -> mixing_actual_compound = CT + CC + CRT + NCC + NCT + NRT (Compound side)
    2. Cycle Tube Summary -> actual_mixing_compound = Air Bag & Tar + Cycle Tube (Compound side)
    3. Auto Tyre Summary  -> mixing_actual_compound = Moulding Tube + Auto Tyre + LCV Tyre + Auto Calender + Tractor (Rubber side)
    """
    try:
        from cycletyres.models import CycleTyreDailyManualEntry
        from cycletube.models import CycleTubeDailyManualEntry
        from stock.models import DailyProductionManualEntry

        entry_date = entry.date

        # 1. Cycle Tyre: CT + CC + CRT + NCC + NCT + NRT (Compound Side)
        cycle_tyre_mix = (
            (entry.compound_ct or Decimal("0.00"))
            + (entry.compound_cc or Decimal("0.00"))
            + (entry.compound_crt or Decimal("0.00"))
            + (entry.compound_ncc or Decimal("0.00"))
            + (entry.compound_nct or Decimal("0.00"))
            + (entry.compound_nrt or Decimal("0.00"))
        )
        ct_entry, _ = CycleTyreDailyManualEntry.objects.get_or_create(date=entry_date)
        ct_entry.mixing_actual_compound = cycle_tyre_mix
        ct_entry.save()

        # 2. Cycle Tube: Air Bag & Tar + Cycle Tube + Moulding Tube (Compound Side)
        cycle_tube_mix = (
            (entry.compound_tar or Decimal("0.00"))
            + (entry.compound_cycle_tube or Decimal("0.00"))
            + (entry.compound_moulding_tube or Decimal("0.00"))
        )
        tube_entry, _ = CycleTubeDailyManualEntry.objects.get_or_create(date=entry_date)
        tube_entry.actual_mixing_compound = cycle_tube_mix
        tube_entry.save()

        # 3. Auto Tyre: Auto Tyre + LCV Tyre + Auto Calender + Tractor (COMPOUND SIDE)
        auto_tyre_mix = (
            (entry.compound_auto_tyre or Decimal("0.00"))
            + (entry.compound_lcv_tyre or Decimal("0.00"))
            + (entry.compound_auto_calender or Decimal("0.00"))
            + (entry.compound_tractor or Decimal("0.00"))
        )
        auto_entry, _ = DailyProductionManualEntry.objects.get_or_create(date=entry_date)
        auto_entry.mixing_actual_compound = auto_tyre_mix
        auto_entry.save()

    except Exception as e:
        print(f"Error syncing mixing to summaries for {entry.date}: {e}")


@api_view(["DELETE"])
@permission_classes([AllowAny])
def delete_mixing_entry(request, entry_id):
    try:
        from decimal import Decimal
        entry = MixingEntry.objects.get(id=entry_id)
        entry_date = entry.date
        entry.delete()

        # Reset daily summary actual mixing compound for this date
        try:
            from cycletyres.models import CycleTyreDailyManualEntry
            from cycletube.models import CycleTubeDailyManualEntry
            from stock.models import DailyProductionManualEntry

            ct = CycleTyreDailyManualEntry.objects.filter(date=entry_date).first()
            if ct:
                ct.mixing_actual_compound = Decimal("0.00")
                ct.save()
            tube = CycleTubeDailyManualEntry.objects.filter(date=entry_date).first()
            if tube:
                tube.actual_mixing_compound = Decimal("0.00")
                tube.save()
            auto = DailyProductionManualEntry.objects.filter(date=entry_date).first()
            if auto:
                auto.mixing_actual_compound = Decimal("0.00")
                auto.save()
        except Exception as sync_err:
            print(f"Error resetting summaries after deleting mixing entry: {sync_err}")

        return Response({"status": "success", "message": "Entry deleted"})
    except MixingEntry.DoesNotExist:
        return Response({"error": "Entry not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([AllowAny])
def export_excel_view(request):
    """
    Exports the exact Excel format as Compound All sheet.
    """
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    month = request.GET.get("month")
    year = request.GET.get("year")
    queryset = MixingEntry.objects.all()
    if month and year:
        queryset = queryset.filter(date__year=int(year), date__month=int(month))
    entries = list(queryset.order_by("date"))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Compound & Rubber"

    # Header styling
    thin_border = Border(
        left=Side(style='thin', color='D0D5DD'),
        right=Side(style='thin', color='D0D5DD'),
        top=Side(style='thin', color='D0D5DD'),
        bottom=Side(style='thin', color='D0D5DD')
    )
    header_fill_compound = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")
    header_fill_rubber = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    header_fill_totals = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")

    # Titles
    ws.merge_cells("A1:N1")
    ws["A1"] = f"COMPOUND MIXING SHEET - {month}/{year}" if month else "COMPOUND MIXING SHEET"
    ws["A1"].font = Font(name="Calibri", size=13, bold=True, color="0369A1")
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("O1:AE1")
    ws["O1"] = f"RUBBER CONSUMPTION & RECONCILIATION - {month}/{year}" if month else "RUBBER RECONCILIATION"
    ws["O1"].font = Font(name="Calibri", size=13, bold=True, color="92400E")
    ws["O1"].alignment = Alignment(horizontal="center")

    # Headers
    headers = [
        # Compound
        "Date", "CT", "CC", "CRT", "NCC", "NCT", "NRT", "Tar/AirBag", "Cycle Tube", "Moulding Tube", "Auto Tyre", "LCV Tyre", "Auto Calender", "Tractor", "Total Compound",
        # Rubber
        "Date", "CT", "CC", "CRT", "NCC", "NCT", "NRT", "Tar/AirBag", "Cycle Tube", "Moulding Tube", "Auto Tyre", "LCV Tyre", "Auto Calender", "Tractor", "Total Rubber",
        # Reconciliation
        "Rubber Bdls", "Rubber Kgs", "Diff"
    ]

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col_num, value=header)
        cell.font = Font(name="Calibri", size=10, bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        if col_num <= 15:
            cell.fill = header_fill_compound
        elif col_num <= 29:
            cell.fill = header_fill_rubber
        else:
            cell.fill = header_fill_totals

    row_num = 3
    for e in entries:
        row_vals = [
            e.date.strftime("%d-%m-%Y"),
            float(e.compound_ct), float(e.compound_cc), float(e.compound_crt), float(e.compound_ncc),
            float(e.compound_nct), float(e.compound_nrt), float(e.compound_tar), float(e.compound_cycle_tube),
            float(e.compound_moulding_tube), float(e.compound_auto_tyre), float(e.compound_lcv_tyre),
            float(e.compound_auto_calender), float(e.compound_tractor), float(e.compound_total),

            e.date.strftime("%d-%m-%Y"),
            float(e.rubber_ct), float(e.rubber_cc), float(e.rubber_crt), float(e.rubber_ncc),
            float(e.rubber_nct), float(e.rubber_nrt), float(e.rubber_tar), float(e.rubber_cycle_tube),
            float(e.rubber_moulding_tube), float(e.rubber_auto_tyre), float(e.rubber_lcv_tyre),
            float(e.rubber_auto_calender), float(e.rubber_tractor), float(e.rubber_total),

            float(e.rubber_bdls), float(e.rubber_kgs), float(e.diff)
        ]
        for col_num, val in enumerate(row_vals, 1):
            c = ws.cell(row=row_num, column=col_num, value=val if val != 0 else "")
            c.border = thin_border
            c.alignment = Alignment(horizontal="center" if col_num in (1, 16) else "right")
        row_num += 1

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="Compound_Mixing_{month or "all"}_{year or ""}.xlsx"'
    wb.save(response)
    return response


# ─── Tally Card / Stock Ledger APIs ───────────────────────────────────────────

from .models import MaterialGroup, Material, StockEntry


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def material_group_list(request):
    """GET: list all groups. POST: create group."""
    if request.method == "GET":
        groups = MaterialGroup.objects.all()
        data = [{"id": g.id, "name": g.name} for g in groups]
        return Response(data)
    name = request.data.get("name", "").strip()
    if not name:
        return Response({"error": "name required"}, status=status.HTTP_400_BAD_REQUEST)
    if MaterialGroup.objects.filter(name=name).exists():
        return Response({"error": "Group already exists"}, status=status.HTTP_400_BAD_REQUEST)
    g = MaterialGroup.objects.create(name=name)
    return Response({"id": g.id, "name": g.name}, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([AllowAny])
def material_group_detail(request, pk):
    """DELETE a group."""
    try:
        g = MaterialGroup.objects.get(pk=pk)
    except MaterialGroup.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    g.delete()
    return Response({"ok": True})




@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def material_list(request):
    """GET: list all materials (optionally filter by group_id). POST: create material."""
    if request.method == "GET":
        group_id = request.GET.get("group_id")
        qs = Material.objects.select_related("group").all()
        if group_id:
            qs = qs.filter(group_id=group_id)
        data = [
            {
                "id": m.id,
                "name": m.name,
                "group_id": m.group_id,
                "group_name": m.group.name,
                "unit": m.unit,
                "minimum_stock": float(m.minimum_stock),
                "standard_rate": float(m.standard_rate or 0),
                "hsn_code": m.hsn_code or "",
            }
            for m in qs
        ]
        return Response(data)
    # POST
    group_id = request.data.get("group_id")
    name = request.data.get("name", "").strip()
    unit = request.data.get("unit", "Kg")
    minimum_stock = request.data.get("minimum_stock", 0)
    standard_rate = request.data.get("standard_rate", 0)
    hsn_code = request.data.get("hsn_code", "").strip()
    if not group_id or not name:
        return Response({"error": "group_id and name required"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        group = MaterialGroup.objects.get(pk=group_id)
    except MaterialGroup.DoesNotExist:
        return Response({"error": "Group not found"}, status=status.HTTP_404_NOT_FOUND)
    m = Material.objects.create(
        group=group,
        name=name,
        unit=unit,
        minimum_stock=minimum_stock or 0,
        standard_rate=standard_rate or 0,
        hsn_code=hsn_code
    )
    return Response({
        "id": m.id,
        "name": m.name,
        "group_id": m.group_id,
        "group_name": group.name,
        "unit": m.unit,
        "minimum_stock": float(m.minimum_stock),
        "standard_rate": float(m.standard_rate),
        "hsn_code": m.hsn_code,
    }, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([AllowAny])
def material_detail(request, pk):
    """DELETE a material."""
    try:
        m = Material.objects.get(pk=pk)
    except Material.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    m.delete()
    return Response({"ok": True})


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def stock_entry_list(request):
    """
    GET: tally ledger — filterable by material_id, from_date, to_date.
    POST: create/update today's stock entry for a material with purchase costing.
    """
    if request.method == "GET":
        qs = StockEntry.objects.select_related("material", "material__group", "created_by").order_by("-date", "-id")
        material_id = request.GET.get("material_id")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        if material_id:
            qs = qs.filter(material_id=material_id)
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)

        today_str = str(datetime.date.today())
        data = []
        for e in qs:
            data.append({
                "id": e.id,
                "date": str(e.date),
                "is_today": str(e.date) == today_str,
                "material_id": e.material_id,
                "material_name": e.material.name,
                "group_name": e.material.group.name,
                "unit": e.material.unit,
                "opening": float(e.opening),
                "received_quantity": float(e.received_quantity),
                "received_by": e.received_by or "",
                "supplier_name": e.supplier_name or "",
                "bill_challan_no": e.bill_challan_no or "",
                "vehicle_no": e.vehicle_no or "",
                "rate_per_unit": float(e.rate_per_unit or 0),
                "total_cost": float(e.total_cost or 0),
                "used_quantity": float(e.used_quantity),
                "closing": float(e.closing),
                "notes": e.notes or "",
                "created_by": e.created_by.get_full_name() or e.created_by.username if e.created_by else "",
            })
        return Response(data)

    # POST - create or update entry
    material_id = request.data.get("material_id")
    date_str = request.data.get("date")
    received_quantity = request.data.get("received_quantity", 0)
    used_quantity = request.data.get("used_quantity", 0)
    received_by = request.data.get("received_by", "")
    supplier_name = request.data.get("supplier_name", "")
    bill_challan_no = request.data.get("bill_challan_no", "")
    vehicle_no = request.data.get("vehicle_no", "")
    rate_per_unit = request.data.get("rate_per_unit", 0)
    notes = request.data.get("notes", "")

    if not material_id or not date_str:
        return Response({"error": "material_id and date required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        material = Material.objects.get(pk=material_id)
    except Material.DoesNotExist:
        return Response({"error": "Material not found"}, status=status.HTTP_404_NOT_FOUND)

    import datetime as dt
    try:
        entry_date = dt.date.fromisoformat(date_str)
    except ValueError:
        return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)

    # Get opening = previous entry's closing
    previous = StockEntry.objects.filter(material=material, date__lt=entry_date).order_by("-date").first()
    opening = previous.closing if previous else Decimal("0")

    entry, created = StockEntry.objects.update_or_create(
        material=material,
        date=entry_date,
        defaults={
            "opening": opening,
            "received_quantity": Decimal(str(received_quantity or 0)),
            "received_by": received_by or "",
            "supplier_name": supplier_name or "",
            "bill_challan_no": bill_challan_no or "",
            "vehicle_no": vehicle_no or "",
            "rate_per_unit": Decimal(str(rate_per_unit or 0)),
            "used_quantity": Decimal(str(used_quantity or 0)),
            "notes": notes or "",
        }
    )

    return Response({
        "id": entry.id,
        "date": str(entry.date),
        "material_id": entry.material_id,
        "material_name": material.name,
        "group_name": material.group.name,
        "unit": material.unit,
        "opening": float(entry.opening),
        "received_quantity": float(entry.received_quantity),
        "received_by": entry.received_by,
        "supplier_name": entry.supplier_name,
        "bill_challan_no": entry.bill_challan_no,
        "vehicle_no": entry.vehicle_no,
        "rate_per_unit": float(entry.rate_per_unit),
        "total_cost": float(entry.total_cost),
        "used_quantity": float(entry.used_quantity),
        "closing": float(entry.closing),
        "notes": entry.notes,
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([AllowAny])
def stock_entry_detail(request, pk):
    """DELETE a stock entry."""
    try:
        e = StockEntry.objects.get(pk=pk)
    except StockEntry.DoesNotExist:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    e.delete()
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([AllowAny])
def bulk_shift_entry(request):
    """
    Bulk save/update an entire day's shift transactions for multiple materials.
    Payload: { "date": "YYYY-MM-DD", "entries": [ { "material_id": 1, "received_quantity": 0, "used_quantity": 50, ... } ] }
    """
    date_str = request.data.get("date")
    entries_data = request.data.get("entries", [])
    if not date_str or not isinstance(entries_data, list):
        return Response({"error": "date and entries array required"}, status=status.HTTP_400_BAD_REQUEST)

    import datetime as dt
    try:
        entry_date = dt.date.fromisoformat(date_str)
    except ValueError:
        return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)

    saved_count = 0
    errors = []

    for item in entries_data:
        mat_id = item.get("material_id")
        if not mat_id:
            continue
        try:
            material = Material.objects.get(pk=mat_id)
        except Material.DoesNotExist:
            errors.append(f"Material {mat_id} not found")
            continue

        recv = Decimal(str(item.get("received_quantity") or 0))
        used = Decimal(str(item.get("used_quantity") or 0))
        rate = Decimal(str(item.get("rate_per_unit") or 0))
        
        # Skip if both are zero and no existing entry
        existing = StockEntry.objects.filter(material=material, date=entry_date).first()
        if recv == 0 and used == 0 and not existing:
            continue

        prev = StockEntry.objects.filter(material=material, date__lt=entry_date).order_by("-date").first()
        opening = prev.closing if prev else Decimal("0")

        StockEntry.objects.update_or_create(
            material=material,
            date=entry_date,
            defaults={
                "opening": opening,
                "received_quantity": recv,
                "used_quantity": used,
                "rate_per_unit": rate,
                "received_by": item.get("received_by", ""),
                "supplier_name": item.get("supplier_name", ""),
                "bill_challan_no": item.get("bill_challan_no", ""),
                "vehicle_no": item.get("vehicle_no", ""),
                "notes": item.get("notes", ""),
            }
        )
        saved_count += 1

    return Response({
        "ok": True,
        "saved_count": saved_count,
        "errors": errors,
        "date": date_str,
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def current_stock_view(request):
    """GET: current stock (latest closing) for all materials, grouped with valuation."""
    groups = MaterialGroup.objects.prefetch_related("materials").all()
    result = []
    total_val = 0.0

    for group in groups:
        items = []
        group_val = 0.0
        for material in group.materials.all():
            last = StockEntry.objects.filter(material=material).order_by("-date", "-id").first()
            closing = float(last.closing) if last else 0.0
            last_date = str(last.date) if last else None
            is_low = closing <= float(material.minimum_stock) and float(material.minimum_stock) > 0
            
            rate = float(last.rate_per_unit) if last and last.rate_per_unit > 0 else float(material.standard_rate or 0)
            item_val = max(0.0, closing * rate)
            group_val += item_val

            items.append({
                "material_id": material.id,
                "material_name": material.name,
                "unit": material.unit,
                "minimum_stock": float(material.minimum_stock),
                "standard_rate": float(material.standard_rate or 0),
                "effective_rate": rate,
                "valuation": round(item_val, 2),
                "closing_stock": closing,
                "last_entry_date": last_date,
                "is_low": is_low,
            })
        total_val += group_val
        result.append({
            "group_id": group.id,
            "group_name": group.name,
            "group_valuation": round(group_val, 2),
            "materials": items,
        })
    return Response({
        "groups": result,
        "total_valuation": round(total_val, 2),
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def stock_forecast_view(request):
    """
    Predictive Run-Out & Days of Inventory Analytics based on 30-day consumption velocity.
    """
    import datetime as dt
    today = dt.date.today()
    thirty_days_ago = today - dt.timedelta(days=30)

    materials = Material.objects.select_related("group").all()
    forecast_list = []
    total_inventory_val = 0.0
    critical_count = 0
    low_count = 0

    for mat in materials:
        last = StockEntry.objects.filter(material=mat).order_by("-date", "-id").first()
        closing = float(last.closing) if last else 0.0
        
        used_30d = StockEntry.objects.filter(
            material=mat,
            date__gte=thirty_days_ago,
            date__lte=today
        ).aggregate(total=Sum("used_quantity"))["total"] or 0
        used_30d = float(used_30d)

        daily_velocity = round(used_30d / 30.0, 2)
        min_stock = float(mat.minimum_stock or 0)
        rate = float(last.rate_per_unit) if last and last.rate_per_unit > 0 else float(mat.standard_rate or 0)
        item_val = max(0.0, closing * rate)
        total_inventory_val += item_val

        if daily_velocity > 0:
            days_left = round(closing / daily_velocity, 1)
            run_out = (today + dt.timedelta(days=int(days_left))).strftime("%d %b %Y") if days_left < 365 else "365+ days"
        else:
            days_left = 999.0 if closing > 0 else 0.0
            run_out = "No Recent Usage" if closing > 0 else "Out of Stock"

        if closing <= 0:
            status_label = "OUT OF STOCK"
            status_color = "#dc2626"
            critical_count += 1
            rec_reorder = max(int(min_stock * 2), 500)
        elif days_left <= 7 or (min_stock > 0 and closing <= min_stock):
            status_label = "CRITICAL"
            status_color = "#dc2626"
            critical_count += 1
            rec_reorder = max(0, int(round((daily_velocity * 30) - closing)))
        elif days_left <= 15:
            status_label = "LOW BUFFER"
            status_color = "#d97706"
            low_count += 1
            rec_reorder = max(0, int(round((daily_velocity * 20) - closing)))
        elif days_left > 90 and closing > 100:
            status_label = "OVERSTOCKED"
            status_color = "#2563eb"
            rec_reorder = 0
        else:
            status_label = "HEALTHY"
            status_color = "#16a34a"
            rec_reorder = 0

        forecast_list.append({
            "material_id": mat.id,
            "material_name": mat.name,
            "group_name": mat.group.name,
            "unit": mat.unit,
            "closing_stock": closing,
            "minimum_stock": min_stock,
            "daily_velocity": daily_velocity,
            "consumption_30d": used_30d,
            "days_left": days_left if days_left != 999.0 else None,
            "run_out_date": run_out,
            "status": status_label,
            "status_color": status_color,
            "recommended_reorder": rec_reorder,
            "effective_rate": rate,
            "valuation": round(item_val, 2),
        })

    forecast_list.sort(key=lambda x: (
        0 if x["status"] in ["OUT OF STOCK", "CRITICAL"] else 1 if x["status"] == "LOW BUFFER" else 2,
        x["days_left"] if x["days_left"] is not None else 9999
    ))

    return Response({
        "forecast": forecast_list,
        "kpis": {
            "total_inventory_value": round(total_inventory_val, 2),
            "critical_count": critical_count,
            "low_count": low_count,
            "total_materials": len(materials),
        }
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def material_passbook_view(request, pk):
    """
    Bank-statement style passbook ledger for a single material.
    GET /api/rawmaterial/materials/<pk>/passbook/?from_date=&to_date=
    """
    try:
        mat = Material.objects.select_related("group").get(pk=pk)
    except Material.DoesNotExist:
        return Response({"error": "Material not found"}, status=status.HTTP_404_NOT_FOUND)

    qs = StockEntry.objects.filter(material=mat).order_by("date", "id")
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    if from_date:
        qs = qs.filter(date__gte=from_date)
    if to_date:
        qs = qs.filter(date__lte=to_date)

    rows = []
    total_inward = 0.0
    total_outward = 0.0
    total_purchase_cost = 0.0

    for e in qs:
        recv = float(e.received_quantity)
        used = float(e.used_quantity)
        cost = float(e.total_cost)
        total_inward += recv
        total_outward += used
        total_purchase_cost += cost

        particulars = []
        if recv > 0:
            if e.supplier_name:
                particulars.append(f"Inward from {e.supplier_name}")
            else:
                particulars.append("Material Purchase Inward")
            if e.bill_challan_no:
                particulars.append(f"Challan #{e.bill_challan_no}")
        if used > 0:
            particulars.append("Plant Mixing Consumption")
        if not particulars:
            particulars.append("Daily Stock Reconciliation")

        rows.append({
            "id": e.id,
            "date": str(e.date),
            "particulars": " • ".join(particulars),
            "supplier_name": e.supplier_name or "",
            "bill_challan_no": e.bill_challan_no or "",
            "vehicle_no": e.vehicle_no or "",
            "opening": float(e.opening),
            "received": recv,
            "rate": float(e.rate_per_unit or 0),
            "cost": cost,
            "used": used,
            "closing": float(e.closing),
            "notes": e.notes or "",
            "received_by": e.received_by or "",
        })

    last_entry = StockEntry.objects.filter(material=mat).order_by("-date", "-id").first()
    curr_stock = float(last_entry.closing) if last_entry else 0.0

    return Response({
        "material": {
            "id": mat.id,
            "name": mat.name,
            "group_name": mat.group.name,
            "unit": mat.unit,
            "minimum_stock": float(mat.minimum_stock),
            "standard_rate": float(mat.standard_rate or 0),
            "current_stock": curr_stock,
        },
        "transactions": rows,
        "totals": {
            "total_inward": round(total_inward, 2),
            "total_outward": round(total_outward, 2),
            "total_purchase_cost": round(total_purchase_cost, 2),
            "entries_count": len(rows),
        }
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def material_passbook_excel(request, pk):
    """
    Download Excel passbook statement for a single material.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    try:
        mat = Material.objects.select_related("group").get(pk=pk)
    except Material.DoesNotExist:
        return Response({"error": "Material not found"}, status=status.HTTP_404_NOT_FOUND)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Passbook_{mat.name[:20]}"

    ws.merge_cells("A1:I1")
    title_cell = ws["A1"]
    title_cell.value = f"RADHU INDUSTRIES — RAW MATERIAL PASSBOOK: {mat.name.upper()} ({mat.unit})"
    title_cell.font = Font(size=14, bold=True, color="FFFFFF")
    title_cell.fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    ws.merge_cells("A2:I2")
    ws["A2"] = f"Category: {mat.group.name} | Unit: {mat.unit} | Min Stock: {mat.minimum_stock} | Standard Rate: Rs {mat.standard_rate}"
    ws["A2"].font = Font(size=10, italic=True, color="475569")
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    headers = ["Date", "Particulars / Description", "Supplier", "Challan / Bill", "Opening", "Inward (+)", "Rate (Rs)", "Outward (-)", "Closing Balance"]
    ws.append([])
    ws.append(headers)
    ws.row_dimensions[4].height = 24

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=4, column=col_idx)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        cell.alignment = Alignment(horizontal="center" if col_idx == 1 else "left")

    qs = StockEntry.objects.filter(material=mat).order_by("date", "id")
    for e in qs:
        recv = float(e.received_quantity)
        used = float(e.used_quantity)
        particulars = f"Inward from {e.supplier_name}" if recv > 0 and e.supplier_name else ("Purchase Inward" if recv > 0 else ("Factory Mixing Used" if used > 0 else "Reconciliation"))
        ws.append([
            str(e.date),
            particulars,
            e.supplier_name or "-",
            e.bill_challan_no or "-",
            float(e.opening),
            recv if recv > 0 else "-",
            float(e.rate_per_unit) if e.rate_per_unit > 0 else "-",
            used if used > 0 else "-",
            float(e.closing),
        ])

    for col_idx, col in enumerate(ws.columns, 1):
        col_letter = get_column_letter(col_idx)
        data_cells = [cell for cell in col[3:] if cell.value is not None]
        max_len = max((len(str(c.value)) for c in data_cells), default=10)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 13)

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="Passbook_{mat.name.replace(" ", "_")}.xlsx"'
    wb.save(response)
    return response


# ─── Dual-Column Daily Stock Sheet (Matching Factory Closing Stock Excel) ─────

LEFT_SECTIONS = [
    "Rubbers",
    "Chemical & Carbon",
    "Processing Oils"
]

RIGHT_SECTIONS = [
    "Fillers",
    "Other Main",
    "Tube Valve",
    "Boiler",
    "Engineering",
    "Miscellaneous"
]


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def daily_stock_sheet_view(request):
    """
    GET: Returns complete factory daily closing stock sheet organized in Left/Right columns.
    POST: Bulk saves/updates all items for the specified date in 1 click.
    """
    if request.method == "GET":
        date_str = request.GET.get("date")
        all_dates_raw = list(
            StockEntry.objects.values_list("date", flat=True).distinct().order_by("-date")
        )
        all_dates = [str(d) for d in all_dates_raw]

        if date_str:
            try:
                target_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            target_date = all_dates_raw[0] if all_dates_raw else datetime.date.today()

        prev_dates = [d for d in all_dates_raw if d < target_date]
        next_dates = [d for d in all_dates_raw if d > target_date]
        prev_date_str = str(prev_dates[0]) if prev_dates else None
        next_date_str = str(next_dates[-1]) if next_dates else None

        groups_qs = MaterialGroup.objects.prefetch_related("materials").all()
        groups_dict = {g.name: g for g in groups_qs}

        today_entries = {e.material_id: e for e in StockEntry.objects.filter(date=target_date)}
        is_saved = len(today_entries) > 0

        tot_opening = 0.0
        tot_received = 0.0
        tot_used = 0.0
        tot_closing = 0.0
        tot_kg = 0.0
        tot_val = 0.0

        def build_section(group_name):
            nonlocal tot_opening, tot_received, tot_used, tot_closing, tot_kg, tot_val
            grp = groups_dict.get(group_name)
            if not grp:
                return {"group_name": group_name, "items": []}

            items = []
            for sno, mat in enumerate(grp.materials.all().order_by("id"), 1):
                entry = today_entries.get(mat.id)
                if entry:
                    opening = float(entry.opening)
                    received = float(entry.received_quantity)
                    used = float(entry.used_quantity)
                    closing = float(entry.closing)
                    rate = float(entry.rate_per_unit or mat.standard_rate or 0)
                    supplier = entry.supplier_name or ""
                    challan = entry.bill_challan_no or ""
                    notes = entry.notes or ""
                else:
                    prev_e = StockEntry.objects.filter(material=mat, date__lt=target_date).order_by("-date").first()
                    opening = float(prev_e.closing) if prev_e else 0.0
                    received = 0.0
                    used = 0.0
                    closing = opening
                    rate = float(mat.standard_rate or 0)
                    supplier = ""
                    challan = ""
                    notes = ""

                per_bag = float(mat.per_bag or 0)
                if per_bag > 0:
                    item_kg = round(closing * per_bag, 2)
                elif mat.unit.lower() == "kg":
                    item_kg = round(closing, 2)
                else:
                    item_kg = 0.0

                item_val = max(0.0, closing * rate) if rate > 0 else 0.0

                tot_opening += opening
                tot_received += received
                tot_used += used
                tot_closing += closing
                tot_kg += item_kg
                tot_val += item_val

                items.append({
                    "sno": sno,
                    "material_id": mat.id,
                    "material_name": mat.name,
                    "unit": mat.unit,
                    "per_bag": per_bag,
                    "opening": opening,
                    "received_quantity": received,
                    "used_quantity": used,
                    "closing": closing,
                    "total_kg": item_kg,
                    "rate_per_unit": rate,
                    "supplier_name": supplier,
                    "bill_challan_no": challan,
                    "notes": notes,
                })
            return {"group_name": group_name, "items": items}

        left_data = [build_section(gn) for gn in LEFT_SECTIONS]
        right_data = [build_section(gn) for gn in RIGHT_SECTIONS]

        total_mats_cnt = sum(len(s["items"]) for s in left_data + right_data)

        return Response({
            "date": str(target_date),
            "is_saved": is_saved,
            "previous_date": prev_date_str,
            "next_date": next_date_str,
            "available_dates": all_dates,
            "kpis": {
                "total_materials": total_mats_cnt,
                "total_opening": round(tot_opening, 2),
                "total_received": round(tot_received, 2),
                "total_used": round(tot_used, 2),
                "total_closing": round(tot_closing, 2),
                "total_kg": round(tot_kg, 2),
                "total_valuation": round(tot_val, 2),
            },
            "left_sections": left_data,
            "right_sections": right_data,
        })

    # POST - Save daily sheet
    date_str = request.data.get("date")
    items_data = request.data.get("items", [])

    if not date_str or not isinstance(items_data, list):
        return Response({"error": "date and items array required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        entry_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return Response({"error": "Invalid date format"}, status=status.HTTP_400_BAD_REQUEST)

    saved_count = 0
    for it in items_data:
        mat_id = it.get("material_id")
        if not mat_id:
            continue
        try:
            mat = Material.objects.get(pk=mat_id)
        except Material.DoesNotExist:
            continue

        prev_e = StockEntry.objects.filter(material=mat, date__lt=entry_date).order_by("-date").first()
        opening = prev_e.closing if prev_e else Decimal("0.00")

        if "closing" in it and it.get("closing") is not None and not it.get("received_quantity") and not it.get("used_quantity"):
            target_closing = Decimal(str(it["closing"]))
            if target_closing < opening:
                recv = Decimal("0.00")
                used = opening - target_closing
            else:
                recv = target_closing - opening
                used = Decimal("0.00")
            closing = target_closing
        else:
            recv = Decimal(str(it.get("received_quantity") or 0))
            used = Decimal(str(it.get("used_quantity") or 0))
            closing = opening + recv - used

        rate = Decimal(str(it.get("rate_per_unit") or 0))

        StockEntry.objects.update_or_create(
            material=mat,
            date=entry_date,
            defaults={
                "opening": opening,
                "received_quantity": recv,
                "used_quantity": used,
                "closing": closing,
                "rate_per_unit": rate,
                "supplier_name": it.get("supplier_name", ""),
                "bill_challan_no": it.get("bill_challan_no", ""),
                "notes": it.get("notes", ""),
            }
        )
        saved_count += 1

    return Response({
        "ok": True,
        "saved_count": saved_count,
        "message": f"Daily stock sheet for {entry_date} successfully saved with {saved_count} items."
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def daily_stock_sheet_excel(request):
    """
    Download Excel sheet for any date matching the factory closing stock layout.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    date_str = request.GET.get("date")
    if date_str:
        try:
            target_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            target_date = datetime.date.today()
    else:
        last = StockEntry.objects.order_by("-date").first()
        target_date = last.date if last else datetime.date.today()

    wb = Workbook()
    ws = wb.active
    ws.title = str(target_date.strftime("%d.%m.%Y"))

    font_title = Font(name="Calibri", size=13, bold=True)
    font_sec = Font(name="Calibri", size=10, bold=True)
    font_hdr = Font(name="Calibri", size=10, bold=True)
    font_data = Font(name="Calibri", size=10)

    fill_sec = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    # Row 1: Title & Date
    ws.merge_cells("B1:F1")
    ws["B1"] = "Raw Materials Stock Position"
    ws["B1"].font = font_title
    ws["B1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("H1:L1")
    ws["H1"] = f"Date : {target_date.strftime('%d /%m/%Y')}"
    ws["H1"].font = font_title
    ws["H1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 25

    # Build Left & Right Data
    groups_qs = MaterialGroup.objects.prefetch_related("materials").all()
    groups_dict = {g.name: g for g in groups_qs}
    today_entries = {e.material_id: e for e in StockEntry.objects.filter(date=target_date)}

    def get_group_rows(group_name):
        grp = groups_dict.get(group_name)
        if not grp:
            return []
        rows = []
        for sno, mat in enumerate(grp.materials.all().order_by("id"), 1):
            e = today_entries.get(mat.id)
            if e:
                qty = float(e.closing)
            else:
                prev_e = StockEntry.objects.filter(material=mat, date__lt=target_date).order_by("-date").first()
                qty = float(prev_e.closing) if prev_e else 0.0
            
            pb = float(mat.per_bag or 0)
            kg_val = round(qty * pb, 2) if pb > 0 else (qty if mat.unit.lower() == "kg" else 0.0)
            rows.append((sno, mat.name, qty, mat.unit, pb if pb > 0 else None, kg_val))
        return rows

    left_rows = []
    for gname in LEFT_SECTIONS:
        left_rows.append(("HEADER", gname.upper()))
        items = get_group_rows(gname)
        left_rows.extend(items)
        left_rows.append(("EMPTY", None))

    right_rows = []
    for gname in RIGHT_SECTIONS:
        right_rows.append(("HEADER", gname.upper()))
        items = get_group_rows(gname)
        right_rows.extend(items)
        right_rows.append(("EMPTY", None))

    max_len = max(len(left_rows), len(right_rows))
    curr_row = 3

    for i in range(max_len):
        l_item = left_rows[i] if i < len(left_rows) else None
        r_item = right_rows[i] if i < len(right_rows) else None

        if l_item:
            if l_item[0] == "HEADER":
                ws.cell(curr_row, 1, "")
                ws.cell(curr_row, 2, l_item[1]).font = font_sec
                ws.cell(curr_row, 3, "Qty").font = font_hdr
                ws.cell(curr_row, 4, "Unit").font = font_hdr
                ws.cell(curr_row, 5, "Per bag").font = font_hdr
                ws.cell(curr_row, 6, "Kg").font = font_hdr
                for c in range(1, 7):
                    ws.cell(curr_row, c).fill = fill_sec
                    ws.cell(curr_row, c).border = thin_border
            elif l_item[0] != "EMPTY":
                sno, name, qty, unit, pb, kg_val = l_item
                ws.cell(curr_row, 1, sno).alignment = Alignment(horizontal="center")
                ws.cell(curr_row, 2, name)
                ws.cell(curr_row, 3, qty).alignment = Alignment(horizontal="right")
                ws.cell(curr_row, 4, unit).alignment = Alignment(horizontal="center")
                ws.cell(curr_row, 5, pb if pb else "").alignment = Alignment(horizontal="right")
                ws.cell(curr_row, 6, kg_val).alignment = Alignment(horizontal="right")
                for c in range(1, 7):
                    ws.cell(curr_row, c).font = font_data
                    ws.cell(curr_row, c).border = thin_border

        if r_item:
            if r_item[0] == "HEADER":
                ws.cell(curr_row, 7, "")
                ws.cell(curr_row, 8, r_item[1]).font = font_sec
                ws.cell(curr_row, 9, "Qty").font = font_hdr
                ws.cell(curr_row, 10, "Unit").font = font_hdr
                ws.cell(curr_row, 11, "Per bag").font = font_hdr
                ws.cell(curr_row, 12, "Kg").font = font_hdr
                for c in range(7, 13):
                    ws.cell(curr_row, c).fill = fill_sec
                    ws.cell(curr_row, c).border = thin_border
            elif r_item[0] != "EMPTY":
                sno, name, qty, unit, pb, kg_val = r_item
                ws.cell(curr_row, 7, sno).alignment = Alignment(horizontal="center")
                ws.cell(curr_row, 8, name)
                ws.cell(curr_row, 9, qty).alignment = Alignment(horizontal="right")
                ws.cell(curr_row, 10, unit).alignment = Alignment(horizontal="center")
                ws.cell(curr_row, 11, pb if pb else "").alignment = Alignment(horizontal="right")
                ws.cell(curr_row, 12, kg_val).alignment = Alignment(horizontal="right")
                for c in range(7, 13):
                    ws.cell(curr_row, c).font = font_data
                    ws.cell(curr_row, c).border = thin_border

        curr_row += 1

    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 32
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 8
    ws.column_dimensions["E"].width = 9
    ws.column_dimensions["F"].width = 12

    ws.column_dimensions["G"].width = 5
    ws.column_dimensions["H"].width = 32
    ws.column_dimensions["I"].width = 10
    ws.column_dimensions["J"].width = 8
    ws.column_dimensions["K"].width = 9
    ws.column_dimensions["L"].width = 12

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="closingstock_{target_date.strftime("%d_%m_%Y")}.xlsx"'
    wb.save(response)
    return response
