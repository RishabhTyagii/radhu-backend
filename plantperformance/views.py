import statistics
import calendar
import datetime
from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PlantPerformanceDailyLog
from .serializers import PlantPerformanceDailyLogSerializer

# External app models
from hrms.models import Attendance, Department
from rawmaterial.models import MixingEntry
from cycletyres.models import CycleTyreEntry, CycleTyreDailyManualEntry
from stock.models import DailyEntry, DailyProductionManualEntry
from cycletube.models import CycleTubeEntry, CycleTubeDailyManualEntry


def safe_div(n, d, decimals=2):
    try:
        if not d or float(d) == 0:
            return 0.0
        val = float(n) / float(d)
        return round(val, decimals)
    except Exception:
        return 0.0


def safe_float(v, decimals=2):
    if v is None:
        return 0.0
    try:
        return round(float(v), decimals)
    except Exception:
        return 0.0


def safe_int(v):
    if v is None:
        return 0
    try:
        return int(v)
    except Exception:
        return 0


def get_dept_attendance(att_qs, dept_names):
    """
    Given a queryset of attendance for a date, filter by matching department names
    and return (man_power, ot, ave_att)
    """
    matched = [a for a in att_qs if a.employee and a.employee.department and a.employee.department.name in dept_names]
    emp_ids = set(a.employee_id for a in matched)
    man_power = len(emp_ids)
    ot = sum(float(a.overtime_hours or 0) for a in matched)
    ave_att = round((man_power * 8.0 + ot) / 8.0, 2) if man_power > 0 or ot > 0 else 0.0
    return man_power, round(ot, 2), ave_att


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def daily_plant_performance(request):
    """
    Returns complete 78-column daily plant performance data for a selected month (YYYY-MM).
    """
    month_str = request.query_params.get("month")
    today = datetime.date.today()

    if month_str:
        try:
            year, month = map(int, month_str.split("-"))
        except ValueError:
            year, month = today.year, today.month
    else:
        year, month = today.year, today.month

    num_days = calendar.monthrange(year, month)[1]
    start_date = datetime.date(year, month, 1)
    end_date = datetime.date(year, month, num_days)

    # 1. Preload HRMS Attendance for the month
    attendances = (
        Attendance.objects.filter(
            date__range=[start_date, end_date],
            status__in=["Present", "Half Day", "Late"],
        )
        .select_related("employee__department")
    )
    att_by_date = {}
    for a in attendances:
        att_by_date.setdefault(a.date, []).append(a)

    # 2. Preload Mixing entries
    mixing_entries = {
        m.date: m for m in MixingEntry.objects.filter(date__range=[start_date, end_date])
    }

    # 3. Preload Cycle Tyre production entries (with tyre item weights)
    ct_entries = (
        CycleTyreEntry.objects.filter(
            entry_type="production", date__range=[start_date, end_date]
        ).select_related("tyre_item")
    )
    ct_curing_by_date = {}
    ct_theo_by_date = {}
    ct_rejection_by_date = {}
    for entry in ct_entries:
        d = entry.date
        curing = entry.all_curing or entry.quantity or 0
        wt = float(entry.tyre_item.weight or 0) if entry.tyre_item else 0.0
        ct_curing_by_date[d] = ct_curing_by_date.get(d, 0) + curing
        ct_theo_by_date[d] = ct_theo_by_date.get(d, 0.0) + (curing * wt)
        ct_rejection_by_date[d] = ct_rejection_by_date.get(d, 0) + (entry.rejected_grade or 0)

    # 4. Preload Cycle Tyre manual entries
    ct_manual_entries = {
        m.date: m for m in CycleTyreDailyManualEntry.objects.filter(date__range=[start_date, end_date])
    }

    # 5. Preload Auto Tyre entries (DailyEntry)
    at_entries = (
        DailyEntry.objects.filter(
            entry_type="production", date__range=[start_date, end_date]
        ).select_related("tyre_item")
    )
    at_curing_by_date = {}
    at_theo_by_date = {}
    at_rejection_by_date = {}
    for entry in at_entries:
        d = entry.date
        curing = entry.all_curing or entry.production_tyre or entry.quantity or 0
        wt = float(entry.tyre_item.weight or 0) if entry.tyre_item else 0.0
        at_curing_by_date[d] = at_curing_by_date.get(d, 0) + curing
        at_theo_by_date[d] = at_theo_by_date.get(d, 0.0) + (curing * wt)
        at_rejection_by_date[d] = at_rejection_by_date.get(d, 0) + (entry.third_grade or 0)

    # 6. Preload Auto Tyre manual entries
    at_manual_entries = {
        m.date: m for m in DailyProductionManualEntry.objects.filter(date__range=[start_date, end_date])
    }

    # 7. Preload Cycle Tube production entries
    tube_entries = (
        CycleTubeEntry.objects.filter(
            entry_type="production", date__range=[start_date, end_date]
        )
    )
    tube_prod_by_date = {}
    for entry in tube_entries:
        d = entry.date
        tube_prod_by_date[d] = tube_prod_by_date.get(d, 0) + (entry.quantity or 0)

    # 8. Preload Cycle Tube manual entries
    tube_manual_entries = {
        m.date: m for m in CycleTubeDailyManualEntry.objects.filter(date__range=[start_date, end_date])
    }

    # 9. Preload PlantPerformanceDailyLog (manual overrides)
    perf_logs = {
        l.date: l for l in PlantPerformanceDailyLog.objects.filter(date__range=[start_date, end_date])
    }

    # Department name lists based on DB setup
    DEPT_WORKSHOP = ["Work Shop", "Workshop"]
    DEPT_BOILER = ["Boiler", "Office & Others", "Office & Others - Airbag", "Bid Wire & Boiler"]
    DEPT_MIXING = ["Chemical", "Mixing"]
    DEPT_CALENDER = ["Calender", "Patti"]
    DEPT_CT_CURING = ["Cycle Press"]
    DEPT_CT_PACKING = ["Tyre Packing C.Y.", "Cycle Tyre Packing"]
    DEPT_AUTO_BUILDING = ["Auto Tyre", "Bead Wire"]
    DEPT_AUTO_CURING = ["Curing Plant"]
    DEPT_TUBE_CURING = ["Tube Plant"]
    DEPT_TUBE_PACKING = ["Tube Packing & Fitting"]

    rows = []
    # For monthly totals / averages
    totals = {}

    for day in range(1, num_days + 1):
        cur_date = datetime.date(year, month, day)
        cur_date_str = cur_date.strftime("%Y-%m-%d")
        day_att = att_by_date.get(cur_date, [])
        log = perf_logs.get(cur_date)

        # 1. WORK SHOP
        ws_mp, ws_ot, ws_ave = get_dept_attendance(day_att, DEPT_WORKSHOP)

        # 2. BOILER/OFFICE/SWEEPER
        bo_mp, bo_ot, bo_ave = get_dept_attendance(day_att, DEPT_BOILER)

        # 3. MIXING
        mix_mp, mix_ot, mix_ave = get_dept_attendance(day_att, DEPT_MIXING)
        mix_entry = mixing_entries.get(cur_date)
        mix_actual = safe_float(mix_entry.compound_total) if mix_entry else 0.0
        mix_variation = safe_float(log.mixing_variation) if log else 0.0
        mix_final = round(mix_actual + mix_variation, 2)

        # 4. PATTI & DAGHA CALENDER
        cal_mp, cal_ot, cal_ave = get_dept_attendance(day_att, DEPT_CALENDER)
        cal_prod_kg = safe_float(log.calender_prod_kg) if log else 0.0
        cal_fab_scrap = safe_float(log.calender_fab_scrap) if log else 0.0
        cal_com_scrap = safe_float(log.calender_com_scrap) if log else 0.0

        # 5. CYCLE TYRE BUILDING
        # MP/OT: if separate or shares with CT Curing/Production
        ct_man = ct_manual_entries.get(cur_date)
        ct_bld_mp = 0
        ct_bld_ot = 0.0
        ct_bld_ave = 0.0
        ct_bld_prod_kg = safe_float(ct_man.parchi_kg) if ct_man else 0.0
        ct_bld_fab_scrap = safe_float(ct_man.calander_bias_cutt) if ct_man else 0.0

        # 6. CYCLE TYRE CURING/PRESS
        ct_cur_mp, ct_cur_ot, ct_cur_ave = get_dept_attendance(day_att, DEPT_CT_CURING)
        ct_cur_prod_num = ct_curing_by_date.get(cur_date, 0)
        ct_cur_pack_num = safe_int(ct_man.packing_pcs) if ct_man else 0
        ct_cur_theo_kg = round(ct_theo_by_date.get(cur_date, 0.0), 2)
        ct_cur_pack_kg = safe_float(ct_man.parchi_kg) if ct_man else 0.0
        ct_cur_variation = round(ct_cur_pack_kg - ct_cur_theo_kg, 2)
        ct_cur_rejection = ct_rejection_by_date.get(cur_date, 0)
        ct_cur_avg_prod = safe_div(ct_cur_prod_num, ct_cur_ave)
        ct_cur_avg_theo = safe_div(ct_cur_theo_kg, ct_cur_ave)
        ct_cur_avg_pack_kg = safe_div(ct_cur_pack_kg, ct_cur_ave)

        # 7. CYCLE TYRE PACKING
        ct_pck_mp, ct_pck_ot, ct_pck_ave = get_dept_attendance(day_att, DEPT_CT_PACKING)
        ct_pck_prod_num = ct_cur_pack_num
        ct_pck_prod_kg = ct_cur_pack_kg
        ct_pck_avg_prod = safe_div(ct_pck_prod_num, ct_pck_ave)
        ct_pck_avg_kg = safe_div(ct_pck_prod_kg, ct_pck_ave)

        # 8. AUTO TYRE BUILDING & BEAD
        at_bld_mp, at_bld_ot, at_bld_ave = get_dept_attendance(day_att, DEPT_AUTO_BUILDING)
        at_bld_prod_num = safe_int(log.auto_building_prod_num) if log else 0
        at_bld_fab_scrap = safe_float(log.auto_building_fab_scrap) if log else 0.0

        # 9. AUTO TYRE CURING & PACKING
        at_cur_mp, at_cur_ot, at_cur_ave = get_dept_attendance(day_att, DEPT_AUTO_CURING)
        at_man = at_manual_entries.get(cur_date)
        at_cur_prod_num = at_curing_by_date.get(cur_date, 0)
        at_cur_pack_num = at_cur_prod_num  # production IS packing for Auto
        at_cur_theo_kg = round(at_theo_by_date.get(cur_date, 0.0), 2)
        at_cur_pack_kg = safe_float(at_man.parchi_kg) if at_man else 0.0
        at_cur_variation = round(at_cur_pack_kg - at_cur_theo_kg, 2)
        at_cur_rejection = at_rejection_by_date.get(cur_date, 0)
        at_cur_avg_prod = safe_div(at_cur_prod_num, at_cur_ave)
        at_cur_avg_theo = safe_div(at_cur_theo_kg, at_cur_ave)
        at_cur_avg_pack_kg = safe_div(at_cur_pack_kg, at_cur_ave)

        # 10. CYCLE TUBE CURING
        tb_cur_mp, tb_cur_ot, tb_cur_ave = get_dept_attendance(day_att, DEPT_TUBE_CURING)
        tb_man = tube_manual_entries.get(cur_date)
        tb_cur_prod_num = tube_prod_by_date.get(cur_date, 0)
        tb_cur_wastage = safe_float(tb_man.total_tube_waste) if tb_man else 0.0
        tb_cur_avg_prod = safe_div(tb_cur_prod_num, tb_cur_ave)

        # 11. CYCLE TUBE PACKING
        tb_pck_mp, tb_pck_ot, tb_pck_ave = get_dept_attendance(day_att, DEPT_TUBE_PACKING)
        tb_pck_cur_prod = tb_cur_prod_num
        tb_pck_pack_prod = tb_cur_prod_num
        tb_pck_pack_kg = safe_float(tb_man.actual_wt_gross) if tb_man else 0.0
        tb_pck_avg_prod = safe_div(tb_pck_pack_prod, tb_pck_ave)
        tb_pck_avg_kg = safe_div(tb_pck_pack_kg, tb_pck_ave)

        # 12. PLANT TOTALS
        total_mp = (
            ws_mp + bo_mp + mix_mp + cal_mp + ct_bld_mp + ct_cur_mp +
            ct_pck_mp + at_bld_mp + at_cur_mp + tb_cur_mp + tb_pck_mp
        )
        total_ot = round(
            ws_ot + bo_ot + mix_ot + cal_ot + ct_bld_ot + ct_cur_ot +
            ct_pck_ot + at_bld_ot + at_cur_ot + tb_cur_ot + tb_pck_ot, 2
        )
        total_ave = round(
            ws_ave + bo_ave + mix_ave + cal_ave + ct_bld_ave + ct_cur_ave +
            ct_pck_ave + at_bld_ave + at_cur_ave + tb_cur_ave + tb_pck_ave, 2
        )

        row = {
            "date": cur_date_str,
            "day": cur_date.strftime("%a"),
            "day_num": day,
            # WORK SHOP
            "ws_mp": ws_mp, "ws_ot": ws_ot, "ws_ave": ws_ave,
            # BOILER
            "bo_mp": bo_mp, "bo_ot": bo_ot, "bo_ave": bo_ave,
            # MIXING
            "mix_mp": mix_mp, "mix_ot": mix_ot, "mix_ave": mix_ave,
            "mix_actual": mix_actual, "mix_final": mix_final, "mix_variation": mix_variation,
            # CALENDER
            "cal_mp": cal_mp, "cal_ot": cal_ot, "cal_ave": cal_ave,
            "cal_prod_kg": cal_prod_kg, "cal_fab_scrap": cal_fab_scrap, "cal_com_scrap": cal_com_scrap,
            # CT BUILDING
            "ct_bld_mp": ct_bld_mp, "ct_bld_ot": ct_bld_ot, "ct_bld_ave": ct_bld_ave,
            "ct_bld_prod_kg": ct_bld_prod_kg, "ct_bld_fab_scrap": ct_bld_fab_scrap,
            # CT CURING
            "ct_cur_mp": ct_cur_mp, "ct_cur_ot": ct_cur_ot, "ct_cur_ave": ct_cur_ave,
            "ct_cur_prod_num": ct_cur_prod_num, "ct_cur_pack_num": ct_cur_pack_num,
            "ct_cur_theo_kg": ct_cur_theo_kg, "ct_cur_pack_kg": ct_cur_pack_kg,
            "ct_cur_variation": ct_cur_variation, "ct_cur_rejection": ct_cur_rejection,
            "ct_cur_avg_prod": ct_cur_avg_prod, "ct_cur_avg_theo": ct_cur_avg_theo,
            "ct_cur_avg_pack_kg": ct_cur_avg_pack_kg,
            # CT PACKING
            "ct_pck_mp": ct_pck_mp, "ct_pck_ot": ct_pck_ot, "ct_pck_ave": ct_pck_ave,
            "ct_pck_prod_num": ct_pck_prod_num, "ct_pck_prod_kg": ct_pck_prod_kg,
            "ct_pck_avg_prod": ct_pck_avg_prod, "ct_pck_avg_kg": ct_pck_avg_kg,
            # AT BUILDING
            "at_bld_mp": at_bld_mp, "at_bld_ot": at_bld_ot, "at_bld_ave": at_bld_ave,
            "at_bld_prod_num": at_bld_prod_num, "at_bld_fab_scrap": at_bld_fab_scrap,
            # AT CURING
            "at_cur_mp": at_cur_mp, "at_cur_ot": at_cur_ot, "at_cur_ave": at_cur_ave,
            "at_cur_prod_num": at_cur_prod_num, "at_cur_pack_num": at_cur_pack_num,
            "at_cur_theo_kg": at_cur_theo_kg, "at_cur_pack_kg": at_cur_pack_kg,
            "at_cur_variation": at_cur_variation, "at_cur_rejection": at_cur_rejection,
            "at_cur_avg_prod": at_cur_avg_prod, "at_cur_avg_theo": at_cur_avg_theo,
            "at_cur_avg_pack_kg": at_cur_avg_pack_kg,
            # TUBE CURING
            "tb_cur_mp": tb_cur_mp, "tb_cur_ot": tb_cur_ot, "tb_cur_ave": tb_cur_ave,
            "tb_cur_prod_num": tb_cur_prod_num, "tb_cur_wastage": tb_cur_wastage,
            "tb_cur_avg_prod": tb_cur_avg_prod,
            # TUBE PACKING
            "tb_pck_mp": tb_pck_mp, "tb_pck_ot": tb_pck_ot, "tb_pck_ave": tb_pck_ave,
            "tb_pck_cur_prod": tb_pck_cur_prod, "tb_pck_pack_prod": tb_pck_pack_prod,
            "tb_pck_pack_kg": tb_pck_pack_kg, "tb_pck_avg_prod": tb_pck_avg_prod,
            "tb_pck_avg_kg": tb_pck_avg_kg,
            # TOTALS
            "total_mp": total_mp, "total_ot": total_ot, "total_ave": total_ave,
            "has_manual": bool(log),
        }
        rows.append(row)

    # Compute monthly totals & averages row
    summary_totals = {}
    sum_keys = [
        "ws_mp", "ws_ot", "ws_ave", "bo_mp", "bo_ot", "bo_ave",
        "mix_mp", "mix_ot", "mix_ave", "mix_actual", "mix_final", "mix_variation",
        "cal_mp", "cal_ot", "cal_ave", "cal_prod_kg", "cal_fab_scrap", "cal_com_scrap",
        "ct_bld_mp", "ct_bld_ot", "ct_bld_ave", "ct_bld_prod_kg", "ct_bld_fab_scrap",
        "ct_cur_mp", "ct_cur_ot", "ct_cur_ave", "ct_cur_prod_num", "ct_cur_pack_num",
        "ct_cur_theo_kg", "ct_cur_pack_kg", "ct_cur_variation", "ct_cur_rejection",
        "ct_pck_mp", "ct_pck_ot", "ct_pck_ave", "ct_pck_prod_num", "ct_pck_prod_kg",
        "at_bld_mp", "at_bld_ot", "at_bld_ave", "at_bld_prod_num", "at_bld_fab_scrap",
        "at_cur_mp", "at_cur_ot", "at_cur_ave", "at_cur_prod_num", "at_cur_pack_num",
        "at_cur_theo_kg", "at_cur_pack_kg", "at_cur_variation", "at_cur_rejection",
        "tb_cur_mp", "tb_cur_ot", "tb_cur_ave", "tb_cur_prod_num", "tb_cur_wastage",
        "tb_pck_mp", "tb_pck_ot", "tb_pck_ave", "tb_pck_cur_prod", "tb_pck_pack_prod",
        "tb_pck_pack_kg", "total_mp", "total_ot", "total_ave",
    ]
    for k in sum_keys:
        summary_totals[k] = round(sum(r[k] for r in rows), 2)

    # Calculate overall averages
    summary_totals["ct_cur_avg_prod"] = safe_div(summary_totals["ct_cur_prod_num"], summary_totals["ct_cur_ave"])
    summary_totals["ct_cur_avg_theo"] = safe_div(summary_totals["ct_cur_theo_kg"], summary_totals["ct_cur_ave"])
    summary_totals["ct_cur_avg_pack_kg"] = safe_div(summary_totals["ct_cur_pack_kg"], summary_totals["ct_cur_ave"])
    summary_totals["ct_pck_avg_prod"] = safe_div(summary_totals["ct_pck_prod_num"], summary_totals["ct_pck_ave"])
    summary_totals["ct_pck_avg_kg"] = safe_div(summary_totals["ct_pck_prod_kg"], summary_totals["ct_pck_ave"])
    summary_totals["at_cur_avg_prod"] = safe_div(summary_totals["at_cur_prod_num"], summary_totals["at_cur_ave"])
    summary_totals["at_cur_avg_theo"] = safe_div(summary_totals["at_cur_theo_kg"], summary_totals["at_cur_ave"])
    summary_totals["at_cur_avg_pack_kg"] = safe_div(summary_totals["at_cur_pack_kg"], summary_totals["at_cur_ave"])
    summary_totals["tb_cur_avg_prod"] = safe_div(summary_totals["tb_cur_prod_num"], summary_totals["tb_cur_ave"])
    summary_totals["tb_pck_avg_prod"] = safe_div(summary_totals["tb_pck_pack_prod"], summary_totals["tb_pck_ave"])
    summary_totals["tb_pck_avg_kg"] = safe_div(summary_totals["tb_pck_pack_kg"], summary_totals["tb_pck_ave"])

    return Response({
        "month": f"{year}-{month:02d}",
        "month_name": calendar.month_name[month],
        "year": year,
        "days_in_month": num_days,
        "rows": rows,
        "totals": summary_totals,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_daily_manual_log(request):
    """
    Saves or updates manual log fields for a date:
    - mixing_variation
    - calender_prod_kg
    - calender_fab_scrap
    - calender_com_scrap
    - auto_building_prod_num
    - auto_building_fab_scrap
    - notes
    """
    date_str = request.data.get("date")
    if not date_str:
        return Response({"error": "date is required"}, status=status.HTTP_400_BAD_REQUEST)

    log, _ = PlantPerformanceDailyLog.objects.get_or_create(date=date_str)

    if "mixing_variation" in request.data:
        log.mixing_variation = Decimal(str(request.data.get("mixing_variation") or 0))
    if "calender_prod_kg" in request.data:
        log.calender_prod_kg = Decimal(str(request.data.get("calender_prod_kg") or 0))
    if "calender_fab_scrap" in request.data:
        log.calender_fab_scrap = Decimal(str(request.data.get("calender_fab_scrap") or 0))
    if "calender_com_scrap" in request.data:
        log.calender_com_scrap = Decimal(str(request.data.get("calender_com_scrap") or 0))
    if "auto_building_prod_num" in request.data:
        log.auto_building_prod_num = int(request.data.get("auto_building_prod_num") or 0)
    if "auto_building_fab_scrap" in request.data:
        log.auto_building_fab_scrap = Decimal(str(request.data.get("auto_building_fab_scrap") or 0))
    if "notes" in request.data:
        log.notes = request.data.get("notes") or ""

    log.save()
    return Response(PlantPerformanceDailyLogSerializer(log).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_summary_rollup(request):
    """
    Returns high-level department roll-up summary matching Sheet1 of the Excel workbook.
    """
    # Reuse daily_plant_performance to compute the monthly rollup
    res = daily_plant_performance(request._request)
    data = res.data
    totals = data.get("totals", {})

    departments = [
        {
            "name": "Mixing",
            "manpower_total": totals.get("mix_mp", 0),
            "ot_total": totals.get("mix_ot", 0),
            "ave_att": totals.get("mix_ave", 0),
            "prod_units": f"{totals.get('mix_final', 0):,.2f} Kg",
            "avg_per_manpower": safe_div(totals.get("mix_final", 0), totals.get("mix_ave", 0)),
        },
        {
            "name": "Patti & Dagha Calender",
            "manpower_total": totals.get("cal_mp", 0),
            "ot_total": totals.get("cal_ot", 0),
            "ave_att": totals.get("cal_ave", 0),
            "prod_units": f"{totals.get('cal_prod_kg', 0):,.2f} Kg",
            "avg_per_manpower": safe_div(totals.get("cal_prod_kg", 0), totals.get("cal_ave", 0)),
        },
        {
            "name": "Cycle Tyre Curing",
            "manpower_total": totals.get("ct_cur_mp", 0),
            "ot_total": totals.get("ct_cur_ot", 0),
            "ave_att": totals.get("ct_cur_ave", 0),
            "prod_units": f"{totals.get('ct_cur_prod_num', 0):,} Pcs",
            "avg_per_manpower": totals.get("ct_cur_avg_prod", 0),
        },
        {
            "name": "Cycle Tyre Packing",
            "manpower_total": totals.get("ct_pck_mp", 0),
            "ot_total": totals.get("ct_pck_ot", 0),
            "ave_att": totals.get("ct_pck_ave", 0),
            "prod_units": f"{totals.get('ct_pck_prod_num', 0):,} Pcs",
            "avg_per_manpower": totals.get("ct_pck_avg_prod", 0),
        },
        {
            "name": "Auto Tyre Building",
            "manpower_total": totals.get("at_bld_mp", 0),
            "ot_total": totals.get("at_bld_ot", 0),
            "ave_att": totals.get("at_bld_ave", 0),
            "prod_units": f"{totals.get('at_bld_prod_num', 0):,} Pcs",
            "avg_per_manpower": safe_div(totals.get("at_bld_prod_num", 0), totals.get("at_bld_ave", 0)),
        },
        {
            "name": "Auto Tyre Curing",
            "manpower_total": totals.get("at_cur_mp", 0),
            "ot_total": totals.get("at_cur_ot", 0),
            "ave_att": totals.get("at_cur_ave", 0),
            "prod_units": f"{totals.get('at_cur_prod_num', 0):,} Pcs",
            "avg_per_manpower": totals.get("at_cur_avg_prod", 0),
        },
        {
            "name": "Cycle Tube Curing",
            "manpower_total": totals.get("tb_cur_mp", 0),
            "ot_total": totals.get("tb_cur_ot", 0),
            "ave_att": totals.get("tb_cur_ave", 0),
            "prod_units": f"{totals.get('tb_cur_prod_num', 0):,} Pcs",
            "avg_per_manpower": totals.get("tb_cur_avg_prod", 0),
        },
        {
            "name": "Cycle Tube Packing",
            "manpower_total": totals.get("tb_pck_mp", 0),
            "ot_total": totals.get("tb_pck_ot", 0),
            "ave_att": totals.get("tb_pck_ave", 0),
            "prod_units": f"{totals.get('tb_pck_pack_prod', 0):,} Pcs",
            "avg_per_manpower": totals.get("tb_pck_avg_prod", 0),
        },
        {
            "name": "Work Shop",
            "manpower_total": totals.get("ws_mp", 0),
            "ot_total": totals.get("ws_ot", 0),
            "ave_att": totals.get("ws_ave", 0),
            "prod_units": "-",
            "avg_per_manpower": "-",
        },
        {
            "name": "Boiler / Office / Sweeper",
            "manpower_total": totals.get("bo_mp", 0),
            "ot_total": totals.get("bo_ot", 0),
            "ave_att": totals.get("bo_ave", 0),
            "prod_units": "-",
            "avg_per_manpower": "-",
        },
    ]

    return Response({
        "month": data.get("month"),
        "month_name": data.get("month_name"),
        "year": data.get("year"),
        "total_manpower": totals.get("total_mp", 0),
        "total_ot": totals.get("total_ot", 0),
        "total_ave_att": totals.get("total_ave", 0),
        "departments": departments,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def plant_advanced_analytics(request):
    """
    Advanced Factory Intelligence & Predictive Analytics Endpoint.
    Grounded strictly in RDS MySQL models: Mixing, Cycle Tyre, Auto Tyre, Cycle Tube, and HRMS.
    """
    month_str = request.query_params.get("month")
    today = datetime.date.today()

    if month_str:
        try:
            year, month = map(int, month_str.split("-"))
        except ValueError:
            year, month = today.year, today.month
    else:
        year, month = today.year, today.month

    # Previous month string
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    prev_month_str = f"{prev_year}-{prev_month:02d}"

    # Query current month and previous month
    cur_res = daily_plant_performance(request._request).data
    
    # Fake request for previous month
    from rest_framework.test import APIRequestFactory
    req_prev = APIRequestFactory().get(f"/api/plant-performance/daily/?month={prev_month_str}")
    req_prev.user = request.user
    prev_res = daily_plant_performance(req_prev).data

    c_tot = cur_res.get("totals", {})
    p_tot = prev_res.get("totals", {})
    rows = cur_res.get("rows", [])

    # 1. Month-on-Month Comparison
    def mom_delta(curr_val, prev_val, round_digits=1):
        c = float(curr_val or 0)
        p = float(prev_val or 0)
        diff = c - p
        pct = (diff / p * 100) if p != 0 else (100.0 if c > 0 else 0.0)
        return {
            "current": round(c, round_digits),
            "previous": round(p, round_digits),
            "diff": round(diff, round_digits),
            "pct": round(pct, 1),
            "direction": "up" if diff > 0 else ("down" if diff < 0 else "neutral"),
        }

    mom = {
        "cycle_tyre_curing": mom_delta(c_tot.get("ct_cur_prod_num"), p_tot.get("ct_cur_prod_num"), 0),
        "auto_tyre_curing": mom_delta(c_tot.get("at_cur_prod_num"), p_tot.get("at_cur_prod_num"), 0),
        "tube_curing": mom_delta(c_tot.get("tb_cur_prod_num"), p_tot.get("tb_cur_prod_num"), 0),
        "mixing_output_kg": mom_delta(c_tot.get("mix_final"), p_tot.get("mix_final"), 2),
        "total_manpower": mom_delta(c_tot.get("total_mp"), p_tot.get("total_mp"), 0),
        "total_overtime_hrs": mom_delta(c_tot.get("total_ot"), p_tot.get("total_ot"), 1),
        "calender_prod_kg": mom_delta(c_tot.get("cal_prod_kg"), p_tot.get("cal_prod_kg"), 2),
    }

    # 2. Plant Intelligence Summaries
    ct_curing = c_tot.get("ct_cur_prod_num", 0) or 0
    ct_packed = c_tot.get("ct_pck_prod_num", 0) or 0
    ct_rejection = c_tot.get("ct_cur_tot_rej", 0) or 0
    ct_rej_rate = safe_div(ct_rejection * 100, ct_curing)
    ct_packing_efficiency = safe_div(ct_packed * 100, ct_curing)

    at_curing = c_tot.get("at_cur_prod_num", 0) or 0
    at_building = c_tot.get("at_bld_prod_num", 0) or 0
    at_rejection = c_tot.get("at_cur_tot_rej", 0) or 0
    at_rej_rate = safe_div(at_rejection * 100, at_curing)
    at_build_cure_gap = at_curing - at_building

    tube_curing = c_tot.get("tb_cur_prod_num", 0) or 0
    tube_packed = c_tot.get("tb_pck_pack_prod", 0) or 0
    tube_scrap = c_tot.get("tb_pck_scrap", 0) or 0
    tube_packing_efficiency = safe_div(tube_packed * 100, tube_curing)

    mix_final = c_tot.get("mix_final", 0) or 0
    mix_actual = c_tot.get("mix_actual", 0) or 0
    mix_variation = c_tot.get("mix_variation", 0) or 0
    cal_fab_scrap = c_tot.get("cal_fab_scrap", 0) or 0
    cal_com_scrap = c_tot.get("cal_com_scrap", 0) or 0
    at_fab_scrap = c_tot.get("at_bld_fab_scrap", 0) or 0
    total_scrap_kg = cal_fab_scrap + cal_com_scrap + at_fab_scrap + tube_scrap

    ct_theo = c_tot.get("ct_cur_theo_con", 0) or 0
    at_theo = c_tot.get("at_cur_theo_con", 0) or 0
    total_theo_compound = ct_theo + at_theo
    compound_buffer_kg = mix_final - total_theo_compound

    plant_summaries = {
        "cycle_tyre": {
            "curing_total": ct_curing,
            "packing_total": ct_packed,
            "rejection_total": ct_rejection,
            "rejection_rate_pct": ct_rej_rate,
            "packing_efficiency_pct": ct_packing_efficiency,
            "wip_accumulation": max(0, ct_curing - ct_packed),
            "avg_output_per_worker": c_tot.get("ct_cur_avg_prod", 0),
        },
        "auto_tyre": {
            "curing_total": at_curing,
            "building_total": at_building,
            "rejection_total": at_rejection,
            "rejection_rate_pct": at_rej_rate,
            "building_curing_gap": at_build_cure_gap,
            "avg_output_per_worker": c_tot.get("at_cur_avg_prod", 0),
        },
        "cycle_tube": {
            "curing_total": tube_curing,
            "packing_total": tube_packed,
            "scrap_total_kg": tube_scrap,
            "packing_efficiency_pct": tube_packing_efficiency,
            "avg_output_per_worker": c_tot.get("tb_cur_avg_prod", 0),
        },
        "mixing": {
            "final_compound_kg": mix_final,
            "actual_mixed_kg": mix_actual,
            "mixing_variation_kg": mix_variation,
            "total_scrap_kg": total_scrap_kg,
            "theoretical_demand_kg": total_theo_compound,
            "buffer_generated_kg": compound_buffer_kg,
            "scrap_rate_pct": safe_div(total_scrap_kg * 100, mix_final),
        },
    }

    # 3. Daily Trends (Time Series)
    daily_trends = []
    total_tyres_list = []

    for r in rows:
        d_str = r.get("date")
        ct_c = r.get("ct_cur_prod_num", 0) or 0
        at_c = r.get("at_cur_prod_num", 0) or 0
        tb_c = r.get("tb_cur_prod_num", 0) or 0
        m_kg = r.get("mix_final", 0) or 0
        tot_tyres = ct_c + at_c
        total_tyres_list.append(tot_tyres)

        daily_trends.append({
            "date": d_str,
            "day": r.get("day"),
            "cycle_tyre": ct_c,
            "auto_tyre": at_c,
            "tube": tb_c,
            "mixing_kg": m_kg,
            "total_tyres": tot_tyres,
            "manpower": r.get("total_mp", 0),
            "ot_hours": r.get("total_ot", 0),
        })

    # 7-day rolling average
    rolling_7d = []
    for i in range(len(total_tyres_list)):
        start_idx = max(0, i - 6)
        window = total_tyres_list[start_idx : i + 1]
        rolling_7d.append(round(sum(window) / len(window), 1) if window else 0)

    for idx, dt in enumerate(daily_trends):
        dt["rolling_7d_avg"] = rolling_7d[idx]

    # 4. Statistical Anomalies
    anomalies = []
    active_ct = [x["cycle_tyre"] for x in daily_trends if x["cycle_tyre"] > 0]
    if len(active_ct) > 2:
        mean_ct = statistics.mean(active_ct)
        std_ct = statistics.stdev(active_ct)
        for r in rows:
            val = r.get("ct_cur_prod_num", 0) or 0
            if val > 0 and (val < mean_ct - 2 * std_ct or val > mean_ct + 2 * std_ct):
                anomalies.append({
                    "date": r.get("date"),
                    "type": "statistical_outlier",
                    "severity": "high" if val < mean_ct - 2 * std_ct else "info",
                    "title": f"Cycle Tyre Curing Output Deviation ({val:,} pcs)",
                    "detail": f"Output on {r.get('date')} differed by {val - mean_ct:+.0f} pcs from month mean ({mean_ct:.0f} ± {std_ct:.0f}).",
                })

    for r in rows:
        ot = r.get("total_ot", 0) or 0
        tot_tyres = (r.get("ct_cur_prod_num", 0) or 0) + (r.get("at_cur_prod_num", 0) or 0)
        if ot > 50 and tot_tyres == 0:
            anomalies.append({
                "date": r.get("date"),
                "type": "operational_disconnect",
                "severity": "warning",
                "title": f"High Overtime with Zero Production on {r.get('date')}",
                "detail": f"{ot} OT hours logged while tyre production was 0 pcs (Possible maintenance or setup shift).",
            })

    daily_scraps = []
    for r in rows:
        sc = (r.get("cal_fab_scrap", 0) or 0) + (r.get("cal_com_scrap", 0) or 0) + (r.get("at_bld_fab_scrap", 0) or 0)
        if sc > 0:
            daily_scraps.append((r.get("date"), sc))
    if daily_scraps:
        sc_vals = [s[1] for s in daily_scraps]
        avg_sc = statistics.mean(sc_vals)
        for d_str, sc in daily_scraps:
            if sc > avg_sc * 1.8 and sc > 50:
                anomalies.append({
                    "date": d_str,
                    "type": "scrap_spike",
                    "severity": "warning",
                    "title": f"Fabric/Compound Scrap Spike ({sc:.1f} kg)",
                    "detail": f"Scrap was {sc - avg_sc:+.1f} kg above daily average ({avg_sc:.1f} kg).",
                })

    # 5. Bottlenecks
    bottlenecks = []
    if ct_curing > 0 and ct_packed > 0:
        wip = ct_curing - ct_packed
        if wip > 5000:
            bottlenecks.append({
                "area": "Cycle Tyre Packing Floor",
                "severity": "medium",
                "title": f"Cycle Tyre WIP Accumulation ({wip:,} pcs)",
                "observation": f"Total cured tyres ({ct_curing:,}) exceeded packed tyres ({ct_packed:,}). Unpacked tyres sitting on floor.",
                "action": "Align packing department shift hours or manpower with curing press velocity.",
            })

    if at_curing > 0 and at_building > 0:
        gap = at_curing - at_building
        if abs(gap) > 1000:
            bottlenecks.append({
                "area": "Auto Tyre Building vs Curing Press",
                "severity": "high" if gap > 0 else "medium",
                "title": f"Auto Tyre Building/Curing Imbalance ({abs(gap):,} pcs)",
                "observation": f"Curing ({at_curing:,} pcs) vs Building ({at_building:,} pcs) mismatch by {gap:+,} pcs.",
                "action": "Audit green tyre buffer stock between building and curing stages.",
            })

    if compound_buffer_kg < -2000:
        bottlenecks.append({
            "area": "Banbury / Mixing Mill Capacity",
            "severity": "high",
            "title": f"Theoretical Compound Deficit ({abs(compound_buffer_kg):,.0f} kg)",
            "observation": f"Theoretical curing demand ({total_theo_compound:,.0f} kg) exceeded mixing output ({mix_final:,.0f} kg).",
            "action": "Increase masterbatch mixing batches to avoid curing press starvation.",
        })

    # 6. Management Recommendations
    recommendations = []
    ct_growth = mom["cycle_tyre_curing"]["pct"]
    at_growth = mom["auto_tyre_curing"]["pct"]
    recommendations.append({
        "category": "Volume & Throughput Momentum",
        "badge": "Positive Momentum" if ct_growth >= 0 else "Decline Alert",
        "badge_color": "emerald" if ct_growth >= 0 else "rose",
        "headline": f"Tyre Output expanded: Cycle Tyre {ct_growth:+.1f}%, Auto Tyre {at_growth:+.1f}% MoM.",
        "text": f"Plant achieved total tyre curing of {ct_curing + at_curing:,} pcs in {cur_res.get('month_name')} {year} compared to {p_tot.get('ct_cur_prod_num', 0) + p_tot.get('at_cur_prod_num', 0):,} pcs in {prev_month_str}.",
    })

    if total_scrap_kg > 0:
        recommendations.append({
            "category": "Material Yield & Scrap Minimization",
            "badge": "Scrap Audit",
            "badge_color": "amber",
            "headline": f"Total recorded plant scrap stands at {total_scrap_kg:,.1f} kg ({plant_summaries['mixing']['scrap_rate_pct']:.2f}% of mixing output).",
            "text": f"Calender Fabric scrap contributed {cal_fab_scrap:,.1f} kg and Compound scrap {cal_com_scrap:,.1f} kg. Implement die edge trim calibration to reduce edge loss.",
        })

    tot_ot = c_tot.get("total_ot", 0) or 0
    tot_mp = c_tot.get("total_mp", 0) or 0
    if tot_mp > 0:
        ot_per_worker = round(tot_ot / tot_mp, 1)
        recommendations.append({
            "category": "Workforce & Overtime Rationalization",
            "badge": "Manpower Efficiency",
            "badge_color": "blue",
            "headline": f"Plant Overtime averaged {ot_per_worker} hours per logged attendee.",
            "text": f"Total overtime hours reached {tot_ot:,.1f} hrs across {cur_res.get('month_name')}. Ensure overtime shifts correlate directly with high-volume curing runs.",
        })

    return Response({
        "status": "success",
        "month": f"{year}-{month:02d}",
        "month_name": cur_res.get("month_name"),
        "year": year,
        "prev_month": prev_month_str,
        "mom_comparison": mom,
        "plant_summaries": plant_summaries,
        "daily_trends": daily_trends,
        "anomalies": anomalies,
        "bottlenecks": bottlenecks,
        "recommendations": recommendations,
    })


from .intelligence_service import get_factory_intelligence_data

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def factory_intelligence_api(request):
    """
    Complete Factory Intelligence Endpoint across all 8 Workspaces.
    Strictly read-only via analytics_readonly connection with field-level RBAC.
    """
    month_str = request.query_params.get("month")
    data = get_factory_intelligence_data(month_str=month_str, user=request.user)
    return Response(data)
