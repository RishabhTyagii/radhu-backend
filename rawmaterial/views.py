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
        entry = MixingEntry.objects.get(id=entry_id)
        entry.delete()
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
