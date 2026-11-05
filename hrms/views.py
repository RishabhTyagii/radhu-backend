import datetime
import re
from decimal import Decimal
from calendar import monthrange

from django.db import transaction
from django.db.models import Sum, Q, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import (
    Department, Employee, LeaveBalance, Attendance, Production,
    Advance, Bonus, Deduction, Salary, WorkerItemRate,
)
from .serializers import (
    DepartmentSerializer, EmployeeSerializer, AttendanceSerializer,
    ProductionSerializer, AdvanceSerializer, BonusSerializer,
    DeductionSerializer, SalarySerializer,
)

# Dashboard
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    today = datetime.date.today()
    total_employees = Employee.objects.filter(status="Active").count()
    total_departments = Department.objects.count()

    today_present = Attendance.objects.filter(date=today, status__in=["Present", "Half Day"]).count()
    today_absent = Attendance.objects.filter(date=today, status="Absent").count()

    month_start = today.replace(day=1)
    month_salary = Salary.objects.filter(month=today.month, year=today.year).aggregate(total=Sum("net_salary"))["total"] or 0

    recent_attendance = Attendance.objects.filter(date=today).select_related("employee", "employee__department")[:10]
    recent_employees = Employee.objects.all().order_by("-created_at")[:5]

    return Response({
        "stats": {
            "total_employees": total_employees,
            "total_departments": total_departments,
            "today_present": today_present,
            "today_absent": today_absent,
            "month_salary": str(month_salary),
        },
        "recent_attendance": AttendanceSerializer(recent_attendance, many=True).data,
        "recent_employees": EmployeeSerializer(recent_employees, many=True).data,
    })


# Departments
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def department_list(request):
    if request.method == "GET":
        deps = Department.objects.all()
        return Response(DepartmentSerializer(deps, many=True).data)

    serializer = DepartmentSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def department_detail(request, pk):
    dep = get_object_or_404(Department, pk=pk)
    if request.method == "DELETE":
        dep.delete()
        return Response({"ok": True})

    serializer = DepartmentSerializer(dep, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Employees
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def employee_list(request):
    if request.method == "GET":
        status_filter = request.query_params.get("status", "Active")
        dept_id = request.query_params.get("department")
        search = request.query_params.get("search", "").strip()

        qs = Employee.objects.all()
        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(employee_code__icontains=search) |
                Q(mobile__icontains=search) |
                Q(designation__icontains=search)
            )

        return Response(EmployeeSerializer(qs, many=True).data)

    serializer = EmployeeSerializer(data=request.data)
    if serializer.is_valid():
        emp = serializer.save()
        LeaveBalance.objects.get_or_create(employee=emp, year=datetime.date.today().year, defaults={"cl_balance": 7, "el_balance": 13})
        return Response(EmployeeSerializer(emp).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def employee_detail(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    if request.method == "DELETE":
        emp.delete()
        return Response({"ok": True})
    elif request.method in ["PUT", "PATCH"]:
        serializer = EmployeeSerializer(emp, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # GET - Full Employee Detail with month-wise attendance, production, leave balance, salary
    today = datetime.date.today()
    month_param = request.query_params.get("month", f"{today.year}-{today.month:02d}")
    try:
        parts = month_param.split("-")
        year, month = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        year, month = today.year, today.month

    # Attendance for month
    attendance_qs = Attendance.objects.filter(employee=emp, date__year=year, date__month=month).order_by("date")
    present_days = attendance_qs.filter(status="Present").count()
    half_days = attendance_qs.filter(status="Half Day").count()
    absent_days = attendance_qs.filter(status="Absent").count()
    total_work_hrs = attendance_qs.aggregate(t=Sum("working_hours"))["t"] or Decimal("0")
    total_ot_hrs = attendance_qs.aggregate(t=Sum("overtime_hours"))["t"] or Decimal("0")
    cl_used = attendance_qs.filter(leave_type="CL").count()
    el_used = attendance_qs.filter(leave_type="EL").count()
    lop_days = attendance_qs.filter(leave_type="LOP").count()

    # Leave Balance
    lb, _ = LeaveBalance.objects.get_or_create(employee=emp, year=year, defaults={"cl_balance": 7, "el_balance": 13})

    # Production for month
    production_qs = Production.objects.filter(employee=emp, date__year=year, date__month=month).order_by("date")
    total_prod_qty = production_qs.aggregate(t=Sum("quantity"))["t"] or Decimal("0")
    total_prod_amount = production_qs.aggregate(t=Sum("total_amount"))["t"] or Decimal("0")
    production_days = production_qs.values('date').distinct().count()

    prod_dates = list(production_qs.values_list("date", flat=True))
    att_present_dates = set([a.date for a in attendance_qs if a.status in ["Present", "Holiday", "Half Day"]])
    all_active_dates = att_present_dates.union(set(prod_dates))
    
    absent_dates = set([a.date for a in attendance_qs if a.status == "Absent"])
    real_absent_days = len(absent_dates - set(prod_dates))

    # Salary for month
    salary = Salary.objects.filter(employee=emp, month=month, year=year).first()

    # Advances, Bonuses, Deductions for month
    advances = Advance.objects.filter(employee=emp, date__year=year, date__month=month)
    bonuses = Bonus.objects.filter(employee=emp, date__year=year, date__month=month)
    deductions = Deduction.objects.filter(employee=emp, date__year=year, date__month=month)

    total_advance = advances.aggregate(t=Sum("amount"))["t"] or Decimal("0")
    total_bonus = bonuses.aggregate(t=Sum("amount"))["t"] or Decimal("0")
    total_deduction = deductions.aggregate(t=Sum("amount"))["t"] or Decimal("0")

    # All salary history
    salary_history = Salary.objects.filter(employee=emp).order_by("-year", "-month")[:12]

    return Response({
        "employee": EmployeeSerializer(emp).data,
        "year": year,
        "month": month,
        "month_str": f"{year:04d}-{month:02d}",
        "attendance_stats": {
            "present_days": present_days,
            "half_days": half_days,
            "absent_days": real_absent_days,
            "total_active_days": len(all_active_dates),
            "total_work_hrs": str(total_work_hrs),
            "total_ot_hrs": str(total_ot_hrs),
            "cl_used": cl_used,
            "el_used": el_used,
            "lop_days": lop_days,
        },
        "leave_balance": {
            "cl_balance": lb.cl_balance,
            "el_balance": lb.el_balance,
        },
        "attendance_list": AttendanceSerializer(attendance_qs, many=True).data,
        "production_stats": {
            "total_qty": str(total_prod_qty),
            "total_amount": str(total_prod_amount),
            "production_days": production_days,
        },
        "production_list": ProductionSerializer(production_qs, many=True).data,
        "adjustments": {
            "advances": AdvanceSerializer(advances, many=True).data,
            "bonuses": BonusSerializer(bonuses, many=True).data,
            "deductions": DeductionSerializer(deductions, many=True).data,
            "total_advance": str(total_advance),
            "total_bonus": str(total_bonus),
            "total_deduction": str(total_deduction),
        },
        "current_salary": SalarySerializer(salary).data if salary else None,
        "salary_history": SalarySerializer(salary_history, many=True).data,
    })


# Attendance
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def attendance_list(request):
    if request.method == "GET":
        date_param = request.query_params.get("date") or str(datetime.date.today())
        emp_id = request.query_params.get("employee")

        qs = Attendance.objects.select_related("employee", "employee__department").filter(date=date_param)
        if emp_id:
            qs = qs.filter(employee_id=emp_id)

        return Response({
            "date": date_param,
            "attendance": AttendanceSerializer(qs, many=True).data,
        })

    serializer = AttendanceSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_attendance(request):
    date_val = request.data.get("date") or str(datetime.date.today())
    entries = request.data.get("entries", [])
    
    created_count = 0
    with transaction.atomic():
        for entry in entries:
            emp_id = entry.get("employee_id")
            if not emp_id: continue
            att_status = entry.get("status", "Present")
            wh = Decimal(str(entry.get("working_hours", 8)))
            ot = Decimal(str(entry.get("overtime_hours", 0)))
            leave_type = entry.get("leave_type", "")
            remarks = entry.get("remarks", "").strip()
            
            # Leave Balance adjustment
            year = int(str(date_val).split('-')[0])
            att_obj = Attendance.objects.filter(employee_id=emp_id, date=date_val).first()
            old_leave_type = att_obj.leave_type if att_obj else ""
            
            if old_leave_type != leave_type:
                lb, _ = LeaveBalance.objects.get_or_create(employee_id=emp_id, year=year)
                if old_leave_type == "CL": lb.cl_balance += 1
                elif old_leave_type == "EL": lb.el_balance += 1
                if leave_type == "CL": lb.cl_balance -= 1
                elif leave_type == "EL": lb.el_balance -= 1
                lb.save()
            
            Attendance.objects.update_or_create(
                employee_id=emp_id,
                date=date_val,
                defaults={
                    "status": att_status,
                    "working_hours": wh,
                    "overtime_hours": ot,
                    "leave_type": leave_type,
                    "remarks": remarks,
                    "created_by": request.user,
                }
            )
            created_count += 1
            
    return Response({"ok": True, "count": created_count, "date": date_val})


# Production (Piece-rate work)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def production_list(request):
    if request.method == "GET":
        date_param = request.query_params.get("date")
        emp_id = request.query_params.get("employee")

        qs = Production.objects.select_related("employee").all()
        if date_param:
            qs = qs.filter(date=date_param)
        if emp_id:
            qs = qs.filter(employee_id=emp_id)

        return Response(ProductionSerializer(qs[:100], many=True).data)

    serializer = ProductionSerializer(data=request.data)
    if serializer.is_valid():
        prod = serializer.save(created_by=request.user)
        # Permanently save the rate for this worker+item combination
        if prod.rate and prod.rate > 0:
            from .models import WorkerItemRate
            WorkerItemRate.objects.update_or_create(
                employee=prod.employee,
                product_name=prod.product_name,
                defaults={"rate": prod.rate}
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def production_items(request):
    # Optional: filter by employee to show relevant items for their department
    emp_id = request.query_params.get("employee_id")
    dept_name = ""
    if emp_id:
        try:
            emp = Employee.objects.select_related("department").get(pk=emp_id)
            dept_name = (emp.department.name if emp.department else "").lower()
        except Exception:
            pass

    names = set()

    # For Cycle Press workers — show CycleTyre items only
    if "cycle press" in dept_name:
        try:
            from cycletyres.models import CycleTyreItem
            for ct in CycleTyreItem.objects.filter(is_active=True):
                n = str(ct).strip()
                # Remove weight bracket from name for cleaner display
                import re
                n = re.sub(r'\s*\[.*?kg\]', '', n).strip()
                if n:
                    names.add(n)
        except Exception:
            pass
        return Response(sorted(list(names)))

    # Default: all items from all sources
    try:
        from stock.models import TyreItem
        for t in TyreItem.objects.all():
            n = f"{t.tyre} {t.pattern} {t.type}".strip()
            if n:
                names.add(n)
    except Exception:
        pass

    try:
        from cycletyres.models import CycleTyreItem
        for ct in CycleTyreItem.objects.filter(is_active=True):
            parts = [str(ct.size), str(ct.box_type), str(ct.material), str(ct.brand)]
            n = " ".join(p for p in parts if p and p.strip()).strip()
            if n:
                names.add(n)
    except Exception:
        pass

    try:
        from cycletube.models import CycleTubeItem
        for tu in CycleTubeItem.objects.filter(is_active=True):
            size = getattr(tu, 'size', '')
            brand = getattr(tu, 'brand', '')
            ttype = getattr(tu, 'type', getattr(tu, 'valve_type', ''))
            n = f"{size} {brand} {ttype}".strip()
            if n:
                names.add(n)
    except Exception:
        pass

    return Response(sorted(list(names)))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def production_last_rate(request):
    from .models import WorkerItemRate
    emp_id = request.query_params.get("employee_id")
    product_name = request.query_params.get("product_name")

    if not emp_id or not product_name:
        return Response({"rate": 0})

    # First check permanent WorkerItemRate table
    saved = WorkerItemRate.objects.filter(employee_id=emp_id, product_name__iexact=product_name).first()
    if saved and saved.rate:
        return Response({"rate": str(saved.rate), "source": "saved"})

    # Fallback: last production record
    last_prod = Production.objects.filter(employee_id=emp_id, product_name__iexact=product_name).order_by("-date", "-id").first()
    return Response({"rate": str(last_prod.rate) if last_prod else 0, "source": "history"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def production_detail(request, pk):
    prod = get_object_or_404(Production, pk=pk)
    prod.delete()
    return Response({"ok": True})


# Advance
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def advance_list(request):
    if request.method == "GET":
        qs = Advance.objects.select_related("employee").all()[:100]
        return Response(AdvanceSerializer(qs, many=True).data)

    serializer = AdvanceSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def advance_detail(request, pk):
    adv = get_object_or_404(Advance, pk=pk)
    adv.delete()
    return Response({"ok": True})


# Bonus
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def bonus_list(request):
    if request.method == "GET":
        qs = Bonus.objects.select_related("employee").all()[:100]
        return Response(BonusSerializer(qs, many=True).data)

    serializer = BonusSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def bonus_detail(request, pk):
    bon = get_object_or_404(Bonus, pk=pk)
    bon.delete()
    return Response({"ok": True})


# Deduction
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def deduction_list(request):
    if request.method == "GET":
        qs = Deduction.objects.select_related("employee").all()[:100]
        return Response(DeductionSerializer(qs, many=True).data)

    serializer = DeductionSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def deduction_detail(request, pk):
    ded = get_object_or_404(Deduction, pk=pk)
    ded.delete()
    return Response({"ok": True})


# Salary Engine
def sync_all_cycletyre_entries():
    try:
        from cycletyres.models import CycleTyreEntry
        entries = CycleTyreEntry.objects.filter(linked_employee_id__isnull=False)
        for e in entries:
            try:
                emp = Employee.objects.get(pk=e.linked_employee_id)
            except Employee.DoesNotExist:
                continue
            
            qty = Decimal(str(e.first_grade + e.second_grade)) if (e.first_grade + e.second_grade) > 0 else Decimal(str(e.quantity))
            if qty <= 0:
                continue
            
            prod_name = str(e.tyre_item)
            name_clean = re.sub(r'\s*\[.*?kg\]', '', prod_name, flags=re.IGNORECASE).strip()
            
            r = WorkerItemRate.objects.filter(employee=emp, product_name__iexact=prod_name).first()
            if not r or not r.rate:
                r = WorkerItemRate.objects.filter(employee=emp, product_name__iexact=name_clean).first()
            rate = r.rate if (r and r.rate) else Decimal('0')
            
            if rate == 0:
                p_prev = Production.objects.filter(employee=emp, product_name__iexact=prod_name).exclude(rate=0).first()
                if not p_prev or not p_prev.rate:
                    p_prev = Production.objects.filter(employee=emp, product_name__iexact=name_clean).exclude(rate=0).first()
                if p_prev and p_prev.rate:
                    rate = p_prev.rate

            tot_amt = qty * rate
            rem_tag = 'CTEntry#' + str(e.id)
            
            p = Production.objects.filter(remarks__icontains=rem_tag).first()
            if not p:
                p = Production.objects.filter(employee=emp, date=e.date, product_name=prod_name, quantity=qty).first()
                if not p:
                    p = Production.objects.filter(employee=emp, date=e.date, product_name=prod_name).first()
            
            if p:
                p.employee = emp
                p.date = e.date
                p.product_name = prod_name
                p.quantity = qty
                p.rate = rate
                p.total_amount = tot_amt
                curr_rem = p.remarks or ''
                if rem_tag not in curr_rem:
                    p.remarks = (curr_rem + ' [' + rem_tag + ']').strip()
                p.save()
            else:
                Production.objects.create(
                    employee=emp,
                    date=e.date,
                    product_name=prod_name,
                    quantity=qty,
                    rate=rate,
                    total_amount=tot_amt,
                    remarks='From Cycle Tyre Entry [' + rem_tag + ']'
                )
    except Exception as err:
        print('Error in sync_all_cycletyre_entries:', err)

def recalculate_employee_salaries(emp):
    try:
        months = Production.objects.filter(employee=emp).values_list('date__year', 'date__month').distinct()
        for year, month in months:
            attendances = Attendance.objects.filter(employee=emp, date__year=year, date__month=month)
            present_days = attendances.filter(status='Present').count()
            half_days = attendances.filter(status='Half Day').count()
            holiday_days = attendances.filter(status='Holiday').count()
            cl_days = attendances.filter(leave_type='CL').count()
            el_days = attendances.filter(leave_type='EL').count()
            total_worked_days = (Decimal(str(present_days)) + Decimal(str(holiday_days)) + Decimal(str(cl_days)) + Decimal(str(el_days)) + (Decimal(str(half_days)) * Decimal('0.5')))
            total_ot_hours = attendances.aggregate(tot=Sum('overtime_hours'))['tot'] or Decimal('0')
            overtime_amt = total_ot_hours * (emp.overtime_rate or Decimal('0'))
            
            basis_days = 26
            _, days_in_month = monthrange(year, month)
            per_day_salary = emp.basic_salary / Decimal(str(basis_days)) if (basis_days > 0 and emp.basic_salary > 0) else Decimal('0')
            earned_basic = per_day_salary * total_worked_days
            
            prod_amt = Production.objects.filter(employee=emp, date__year=year, date__month=month).aggregate(tot=Sum('total_amount'))['tot'] or Decimal('0')
            
            dept_name = (emp.department.name if emp.department else '').lower()
            incentive_amt = round(prod_amt * Decimal('0.1562'), 2) if 'cycle press' in dept_name else Decimal('0')
            
            bonus_amt = Bonus.objects.filter(employee=emp, date__year=year, date__month=month).aggregate(tot=Sum('amount'))['tot'] or Decimal('0')
            adv_amt = Advance.objects.filter(employee=emp, date__year=year, date__month=month).aggregate(tot=Sum('amount'))['tot'] or Decimal('0')
            ded_amt = Deduction.objects.filter(employee=emp, date__year=year, date__month=month).aggregate(tot=Sum('amount'))['tot'] or Decimal('0')
            
            gross = round(earned_basic + prod_amt + incentive_amt + overtime_amt, 2)
            pf_amt = round((gross * (emp.pf_percent or Decimal('0'))) / Decimal('100'))
            esi_amt = round((gross * (emp.esi_percent or Decimal('0'))) / Decimal('100'))
            
            net = round((gross + bonus_amt) - (adv_amt + ded_amt + pf_amt + esi_amt))
            net = max(net, Decimal('0'))
            
            Salary.objects.update_or_create(
                employee=emp,
                month=month,
                year=year,
                defaults={
                    'basic_salary': round(earned_basic, 2),
                    'overtime_amount': round(overtime_amt, 2),
                    'production_amount': round(prod_amt, 2),
                    'incentive_amount': round(incentive_amt, 2),
                    'bonus': round(bonus_amt, 2),
                    'advance': round(adv_amt, 2),
                    'deduction': round(ded_amt, 2),
                    'pf_amount': round(pf_amt, 2),
                    'esi_amount': round(esi_amt, 2),
                    'net_salary': round(net, 2),
                }
            )
    except Exception as err:
        print('Error in recalculate_employee_salaries:', err)

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def salary_list(request):
    today = datetime.date.today()
    sync_all_cycletyre_entries()

    if request.method == "POST":
        month = int(request.data.get("month", today.month))
        year = int(request.data.get("year", today.year))
        emp_id = request.data.get("employee")

        employees = Employee.objects.filter(status="Active")
        if emp_id:
            employees = employees.filter(pk=emp_id)

        basis_days = int(request.data.get("basis_days", 26))
        _, days_in_month = monthrange(year, month)
        if basis_days <= 0:
            basis_days = days_in_month
            
        generated_salaries = []

        with transaction.atomic():
            for emp in employees:
                attendances = Attendance.objects.filter(
                    employee=emp, date__year=year, date__month=month
                )
                present_days = attendances.filter(status="Present").count()
                half_days = attendances.filter(status="Half Day").count()
                # Holiday = 1 full paid day
                holiday_days = attendances.filter(status="Holiday").count()
                cl_days = attendances.filter(leave_type="CL").count()
                el_days = attendances.filter(leave_type="EL").count()
                total_worked_days = (Decimal(str(present_days))
                                     + Decimal(str(holiday_days))
                                     + Decimal(str(cl_days))
                                     + Decimal(str(el_days))
                                     + (Decimal(str(half_days)) * Decimal("0.5")))

                total_ot_hours = attendances.aggregate(tot=Sum("overtime_hours"))["tot"] or Decimal("0")
                overtime_amt = total_ot_hours * (emp.overtime_rate or Decimal("0"))

                if basis_days > 0 and emp.basic_salary > 0:
                    per_day_salary = emp.basic_salary / Decimal(str(basis_days))
                    earned_basic = per_day_salary * total_worked_days
                else:
                    earned_basic = Decimal("0")

                prod_amt = Production.objects.filter(
                    employee=emp, date__year=year, date__month=month
                ).aggregate(tot=Sum("total_amount"))["tot"] or Decimal("0")

                # Cycle Press incentive: 15.62% on production amount
                CYCLE_PRESS_INCENTIVE = Decimal("0.1562")
                dept_name = (emp.department.name if emp.department else "").lower()
                incentive_amt = Decimal("0")
                if "cycle press" in dept_name:
                    incentive_amt = round(prod_amt * CYCLE_PRESS_INCENTIVE, 2)

                bonus_amt = Bonus.objects.filter(
                    employee=emp, date__year=year, date__month=month
                ).aggregate(tot=Sum("amount"))["tot"] or Decimal("0")

                adv_amt = Advance.objects.filter(
                    employee=emp, date__year=year, date__month=month
                ).aggregate(tot=Sum("amount"))["tot"] or Decimal("0")

                ded_amt = Deduction.objects.filter(
                    employee=emp, date__year=year, date__month=month
                ).aggregate(tot=Sum("amount"))["tot"] or Decimal("0")

                gross = round(earned_basic + prod_amt + incentive_amt + overtime_amt, 2)
                pf_amt = round((gross * (emp.pf_percent or Decimal("0"))) / Decimal("100"))
                esi_amt = round((gross * (emp.esi_percent or Decimal("0"))) / Decimal("100"))

                net = round((gross + bonus_amt) - (adv_amt + ded_amt + pf_amt + esi_amt))
                net = max(net, Decimal("0"))

                sal, created = Salary.objects.update_or_create(
                    employee=emp,
                    month=month,
                    year=year,
                    defaults={
                        "basic_salary": round(earned_basic, 2),
                        "overtime_amount": round(overtime_amt, 2),
                        "production_amount": round(prod_amt, 2),
                        "incentive_amount": round(incentive_amt, 2),
                        "bonus": round(bonus_amt, 2),
                        "advance": round(adv_amt, 2),
                        "deduction": round(ded_amt, 2),
                        "pf_amount": round(pf_amt, 2),
                        "esi_amount": round(esi_amt, 2),
                        "net_salary": round(net, 2),
                    }
                )
                generated_salaries.append(sal)

        return Response(SalarySerializer(generated_salaries, many=True).data, status=status.HTTP_201_CREATED)

    month = int(request.query_params.get("month", today.month))
    year = int(request.query_params.get("year", today.year))

    salaries = Salary.objects.select_related("employee", "employee__department").filter(month=month, year=year)
    totals = salaries.aggregate(
        total_payout=Sum("net_salary"),
        total_basic=Sum("basic_salary"),
        total_production=Sum("production_amount"),
        total_overtime=Sum("overtime_amount"),
    )

    return Response({
        "month": month,
        "year": year,
        "salaries": SalarySerializer(salaries, many=True).data,
        "totals": {
            "total_payout": str(totals["total_payout"] or 0),
            "total_basic": str(totals["total_basic"] or 0),
            "total_production": str(totals["total_production"] or 0),
            "total_overtime": str(totals["total_overtime"] or 0),
        }
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def salary_slip(request, pk):
    sal = get_object_or_404(Salary.objects.select_related("employee", "employee__department"), pk=pk)
    emp = sal.employee
    _, days_in_month = monthrange(sal.year, sal.month)

    attendances = Attendance.objects.filter(
        employee=emp, date__year=sal.year, date__month=sal.month
    ).order_by("date")

    present_days = attendances.filter(status="Present").count()
    half_days = attendances.filter(status="Half Day").count()
    absent_days = attendances.filter(status="Absent").count()
    cl_days = attendances.filter(leave_type="CL").count()
    el_days = attendances.filter(leave_type="EL").count()
    lop_days = attendances.filter(leave_type="LOP").count()
    holiday_days = attendances.filter(status="Holiday").count()
    week_off_days = attendances.filter(status="Week Off").count()
    total_overtime_hours = sum(float(a.overtime_hours or 0) for a in attendances)

    # Date-wise attendance list
    attendance_detail = []
    for a in attendances:
        attendance_detail.append({
            "date": str(a.date),
            "day": a.date.strftime("%d"),
            "weekday": a.date.strftime("%a"),
            "status": a.status,
            "leave_type": a.leave_type,
            "working_hours": float(a.working_hours or 0),
            "overtime_hours": float(a.overtime_hours or 0),
        })

    # Production records for this month
    from hrms.models import Production
    import re
    sync_all_cycletyre_entries()
    productions = Production.objects.filter(
        employee=emp, date__year=sal.year, date__month=sal.month
    ).order_by("date")

    prod_dates = list(productions.values_list("date", flat=True))
    att_present_dates = set([a.date for a in attendances if a.status in ["Present", "Holiday", "Half Day"]])
    all_active_dates = att_present_dates.union(set(prod_dates))
    
    # Recalculate absent days: days_in_month - all_active_dates - week_off_days
    # But wait, what if they were marked 'Absent' on a day they produced? Let's simply count the days they have NO activity and NO week off.
    # Actually, a simpler way is just: any date with "Absent" mark that is NOT in prod_dates.
    absent_dates = set([a.date for a in attendances if a.status == "Absent"])
    real_absent_days = len(absent_dates - set(prod_dates))

    production_detail = []
    for p in productions:
        clean_name = re.sub(r'\s*\[.*?kg\]', '', p.product_name)
        production_detail.append({
            "date": str(p.date),
            "day": p.date.strftime("%d"),
            "weekday": p.date.strftime("%a"),
            "product_name": clean_name,
            "quantity": float(p.quantity),
            "rate": float(p.rate),
            "total_amount": float(p.total_amount),
            "remarks": p.remarks or "",
        })

    return Response({
        "salary": SalarySerializer(sal).data,
        "employee": EmployeeSerializer(emp).data,
        "attendance_summary": {
            "days_in_month": days_in_month,
            "present_days": present_days,
            "half_days": half_days,
            "absent_days": real_absent_days,
            "holiday_days": holiday_days,
            "cl_days": cl_days,
            "el_days": el_days,
            "lop_days": lop_days,
            "week_off_days": week_off_days,
            "total_worked_days": present_days + holiday_days + cl_days + el_days + (half_days * 0.5),
            "total_active_days": len(all_active_dates),
            "total_overtime_hours": total_overtime_hours,
        },
        "attendance_detail": attendance_detail,
        "production_detail": production_detail,
    })

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_attendance_register(request):
    import datetime
    from calendar import monthrange
    today = datetime.date.today()
    month_str = request.query_params.get("month", f"{today.year}-{today.month:02d}")
    try:
        year = int(str(month_str).split("-")[0])
        month = int(str(month_str).split("-")[1])
    except:
        year = today.year
        month = today.month
        
    dept_id = request.query_params.get("department")

    _, days_in_month = monthrange(year, month)

    emp_qs = Employee.objects.filter(status="Active").select_related("department")
    if dept_id:
        emp_qs = emp_qs.filter(department_id=dept_id)

    att_qs = Attendance.objects.filter(
        date__year=year, date__month=month,
        employee__in=emp_qs
    )

    employees_data = [
        {
            "id": emp.id,
            "name": emp.name,
            "employee_code": emp.employee_code,
        }
        for emp in emp_qs
    ]

    attendance_data = [
        {
            "employee_id": a.employee_id,
            "date": str(a.date),
            "status": a.status,
            "leave_type": a.leave_type,
            "overtime_hours": float(a.overtime_hours or 0)
        }
        for a in att_qs
    ]

    return Response({
        "month": month,
        "year": year,
        "days_in_month": days_in_month,
        "employees": employees_data,
        "attendance": attendance_data,
    })
import datetime
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Employee, Attendance
from .serializers import EmployeeSerializer, AttendanceSerializer

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def attendance_monthly_data(request):
    """
    Expected by frontend: /hrms/attendance/monthly/?month=YYYY-MM&department_id=1
    """
    month_str = request.query_params.get("month") # YYYY-MM
    dept_id = request.query_params.get("department_id")

    if not month_str:
        return Response({"employees": [], "attendance": []})

    y, m = month_str.split('-')
    
    emp_qs = Employee.objects.filter(status="Active")
    if dept_id and str(dept_id).strip():
        emp_qs = emp_qs.filter(department_id=dept_id)

    att_qs = Attendance.objects.filter(
        date__year=y, date__month=m, employee__in=emp_qs
    )

    from hrms.models import Production
    active_days_map = {}
    for emp in emp_qs:
        emp_att = [a for a in att_qs if a.employee_id == emp.id]
        att_present_dates = set([a.date for a in emp_att if a.status in ["Present", "Holiday", "Half Day"]])
        emp_prod_dates = set(Production.objects.filter(employee=emp, date__year=y, date__month=m).values_list("date", flat=True))
        active_days_map[emp.id] = len(att_present_dates.union(emp_prod_dates))

    return Response({
        "employees": EmployeeSerializer(emp_qs, many=True).data,
        "attendance": AttendanceSerializer(att_qs, many=True).data,
        "active_days_map": active_days_map
    })

from django.db import transaction
from decimal import Decimal

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_attendance_any(request):
    entries = request.data.get("entries", [])
    created_count = 0
    with transaction.atomic():
        for entry in entries:
            emp_id = entry.get("employee_id")
            date_val = entry.get("date")
            if not emp_id or not date_val: continue
            
            att_status = entry.get("status", "Present")
            wh = Decimal(str(entry.get("working_hours", 0)))
            ot = Decimal(str(entry.get("overtime_hours", 0)))
            leave_type = entry.get("leave_type", "")
            
            # Leave Balance adjustment
            year = int(str(date_val).split('-')[0])
            att_obj = Attendance.objects.filter(employee_id=emp_id, date=date_val).first()
            old_leave_type = att_obj.leave_type if att_obj else ""
            
            if old_leave_type != leave_type:
                lb, _ = LeaveBalance.objects.get_or_create(employee_id=emp_id, year=year)
                if old_leave_type == "CL": lb.cl_balance += 1
                elif old_leave_type == "EL": lb.el_balance += 1
                if leave_type == "CL": lb.cl_balance -= 1
                elif leave_type == "EL": lb.el_balance -= 1
                lb.save()
            
            Attendance.objects.update_or_create(
                employee_id=emp_id,
                date=date_val,
                defaults={
                    "status": att_status,
                    "working_hours": wh,
                    "overtime_hours": ot,
                    "leave_type": leave_type,
                    "created_by": request.user,
                }
            )
            created_count += 1
            
    return Response({"ok": True, "count": created_count})


# ============================================================
# Worker Item Rates
# ============================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def item_rates_list(request):
    """GET /api/hrms/item-rates/?employee_id=<id>  — list rates for an employee"""
    from .models import WorkerItemRate
    emp_id = request.query_params.get("employee_id")
    if not emp_id:
        return Response({"error": "employee_id required"}, status=400)
    rates = WorkerItemRate.objects.filter(employee_id=emp_id).order_by("product_name")
    data = [
        {
            "id": r.id,
            "product_name": r.product_name,
            "rate": str(r.rate),
            "updated_at": r.updated_at.strftime("%d %b %Y"),
        }
        for r in rates
    ]
    return Response(data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def item_rate_detail(request, pk):
    """PATCH /api/hrms/item-rates/<pk>/  — update a single rate"""
    from .models import WorkerItemRate, Production
    import re
    try:
        r = WorkerItemRate.objects.get(pk=pk)
    except WorkerItemRate.DoesNotExist:
        return Response({"error": "Not found"}, status=404)
    new_rate = request.data.get("rate")
    if new_rate is None:
        return Response({"error": "rate required"}, status=400)
    
    try:
        new_rate_dec = Decimal(str(new_rate))
    except Exception:
        return Response({"error": "invalid rate"}, status=400)
        
    r.rate = new_rate_dec
    r.save()
    
    emp = r.employee
    raw_name = str(r.product_name)
    clean_n = re.sub(r'\s*\[.*?kg\]', '', raw_name, flags=re.IGNORECASE).strip()
    
    prods = Production.objects.filter(employee=emp)
    updated_prods = 0
    for p in prods:
        p_clean = re.sub(r'\s*\[.*?kg\]', '', str(p.product_name), flags=re.IGNORECASE).strip()
        if p.product_name.lower() == raw_name.lower() or p_clean.lower() == clean_n.lower():
            p.rate = new_rate_dec
            p.total_amount = p.quantity * new_rate_dec
            p.save()
            updated_prods += 1
            
    recalculate_employee_salaries(emp)
    
    return Response({"ok": True, "rate": str(r.rate), "updated_productions": updated_prods})

@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def leave_balance_detail(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    year = int(request.query_params.get("year", datetime.date.today().year))
    lb, _ = LeaveBalance.objects.get_or_create(
        employee=emp, year=year,
        defaults={"cl_balance": 7, "el_balance": 13}
    )
    if request.method == "PATCH":
        cl = request.data.get("cl_balance")
        el = request.data.get("el_balance")
        if cl is not None:
            lb.cl_balance = int(cl)
        if el is not None:
            lb.el_balance = int(el)
        lb.save()
    return Response({
        "id": lb.id,
        "employee_id": emp.id,
        "year": lb.year,
        "cl_balance": lb.cl_balance,
        "el_balance": lb.el_balance,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def avg_production_cycle_tyre(request):
    """Daily average production report for Cycle Tyre department.
    
    Query params:
    - from_date: YYYY-MM-DD (default: 30 days ago)
    - to_date: YYYY-MM-DD (default: today)
    - department_id: optional, filter by specific department
    
    Columns per day:
    1. Man Power: count of distinct employees who have attendance (Present/Half Day/Late) for that date
       AND belong to the filtered department (or all production departments)
    2. OT: sum of overtime_hours from Attendance for those employees on that date
    3. Avg Time: (ManPower * 8 + OT) / 8
    4. Production: sum of all_curing from CycleTyreEntry where entry_type='production' for that date
    5. Avg Production: Production / Avg Time (if Avg Time > 0, else 0)
    """
    import datetime
    from django.db.models import Sum, Count, Q
    from cycletyres.models import CycleTyreEntry
    
    today = datetime.date.today()
    from_date_str = request.query_params.get('from_date')
    to_date_str = request.query_params.get('to_date')
    department_id = request.query_params.get('department_id')
    
    if from_date_str:
        try:
            from_date = datetime.datetime.strptime(from_date_str, '%Y-%m-%d').date()
        except ValueError:
            from_date = today - datetime.timedelta(days=30)
    else:
        from_date = today - datetime.timedelta(days=30)
    
    if to_date_str:
        try:
            to_date = datetime.datetime.strptime(to_date_str, '%Y-%m-%d').date()
        except ValueError:
            to_date = today
    else:
        to_date = today
    
    # Build daily data
    daily_data = []
    totals = {'man_power': 0, 'ot': 0, 'avg_time': 0, 'production': 0, 'avg_production': 0, 'days_count': 0}
    
    current = from_date
    while current <= to_date:
        # Man Power: count of distinct employees present on this date
        att_filter = Q(
            date=current,
            status__in=['Present', 'Half Day', 'Late']
        )
        if department_id:
            att_filter &= Q(employee__department_id=department_id)
        
        attendance_qs = Attendance.objects.filter(att_filter)
        man_power = attendance_qs.values('employee').distinct().count()
        
        # OT: sum of overtime_hours
        ot_total = attendance_qs.aggregate(total_ot=Sum('overtime_hours'))['total_ot'] or 0
        ot_total = float(ot_total)
        
        # Avg Time: (ManPower * 8 + OT) / 8
        avg_time = round((man_power * 8 + ot_total) / 8, 2) if man_power > 0 else 0
        
        # Production: sum of all_curing for that date
        production = CycleTyreEntry.objects.filter(
            entry_type='production',
            date=current
        ).aggregate(total=Sum('all_curing'))['total'] or 0
        
        # Avg Production: production / avg_time
        avg_prod = round(production / avg_time, 1) if avg_time > 0 else 0
        
        row = {
            'date': current.strftime('%Y-%m-%d'),
            'day': current.strftime('%a'),
            'man_power': man_power,
            'ot': round(ot_total, 1),
            'avg_time': avg_time,
            'production': production,
            'avg_production': avg_prod,
        }
        daily_data.append(row)
        
        if man_power > 0:
            totals['man_power'] += man_power
            totals['ot'] += ot_total
            totals['avg_time'] += avg_time
            totals['production'] += production
            totals['avg_production'] += avg_prod
            totals['days_count'] += 1
        
        current += datetime.timedelta(days=1)
    
    # Calculate averages for the period
    days = totals['days_count'] or 1
    summary = {
        'avg_man_power': round(totals['man_power'] / days, 1),
        'total_ot': round(totals['ot'], 1),
        'avg_avg_time': round(totals['avg_time'] / days, 2),
        'total_production': totals['production'],
        'avg_daily_production': round(totals['production'] / days, 1),
        'overall_avg_production': round(totals['production'] / totals['avg_time'], 1) if totals['avg_time'] > 0 else 0,
        'working_days': days,
    }
    
    # Get departments list for filter dropdown
    depts = list(Department.objects.all().values('id', 'name'))
    
    return Response({
        'daily_data': daily_data,
        'summary': summary,
        'departments': depts,
        'filters': {
            'from_date': from_date.strftime('%Y-%m-%d'),
            'to_date': to_date.strftime('%Y-%m-%d'),
            'department_id': department_id,
        }
    })



# ==============================================================================
# Cycle Press Production Excel Export (Exact Matrix Format)
# ==============================================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_cycle_press_production_excel(request):
    """
    Exports Cycle Press production for a selected month matching the matrix format
    of CY-TYRE PRODUCTION COMPANY EMP ONLY final.xlsx:
    - One sheet per worker
    - Matrix columns: Tyre Names (Grade A, Grade B)
    - Days 1 to 31
    - Bottom summary block: Sum row, repeated tyre headers, A/B, PRODUCTION (=A+B),
      RATE (per 100 pcs), TOTAL (=Rate*Production/100), TOTAL EARING
    - Incentive block: 15.62% FIX INCENTIVE, TOTAL PRODUCTION EARING, GRAND TOTAL
    """
    import calendar
    import re
    from io import BytesIO
    from django.http import HttpResponse
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    from cycletyres.models import CycleTyreEntry
    from hrms.models import Employee, WorkerItemRate, Production

    today = datetime.date.today()
    month_param = request.query_params.get("month") or request.GET.get("month")
    year_param = request.query_params.get("year") or request.GET.get("year")

    target_year = today.year
    target_month = today.month

    if month_param and "-" in str(month_param):
        try:
            parts = str(month_param).strip().split("-")
            target_year = int(parts[0])
            target_month = int(parts[1])
        except Exception:
            pass
    else:
        if year_param and str(year_param).isdigit():
            target_year = int(year_param)
        if month_param and str(month_param).isdigit():
            target_month = int(month_param)

    # Sync any newly recorded cycle tyre curing entries
    sync_all_cycletyre_entries()

    _, num_days = calendar.monthrange(target_year, target_month)

    # Find all cycle press workers who have entries or productions in this month
    e1 = list(CycleTyreEntry.objects.filter(
        date__year=target_year,
        date__month=target_month,
        linked_employee_id__gt=0
    ).values_list('linked_employee_id', flat=True).distinct())

    e2 = list(Production.objects.filter(
        date__year=target_year,
        date__month=target_month
    ).filter(
        Q(employee__department__name__icontains="Press") | Q(employee__department_id=5)
    ).values_list('employee_id', flat=True).distinct())

    all_emp_ids = sorted(list(set(e1 + e2)))
    employees = list(Employee.objects.filter(id__in=all_emp_ids).order_by("name"))

    if not employees:
        employees = list(Employee.objects.filter(
            Q(department__name__icontains="Press") | Q(department_id=5),
            status="Active"
        ).order_by("name"))

    wb = openpyxl.Workbook()
    default_sheet = wb.active

    thin_border = Border(
        left=Side(style='thin', color='000000'),
        right=Side(style='thin', color='000000'),
        top=Side(style='thin', color='000000'),
        bottom=Side(style='thin', color='000000')
    )
    font_title = Font(name='Calibri', size=18, bold=True)
    font_header = Font(name='Calibri', size=13, bold=True)
    font_sub = Font(name='Calibri', size=13, bold=True)
    font_data = Font(name='Calibri', size=11, bold=False)
    font_total = Font(name='Calibri', size=14, bold=True)
    align_center = Alignment(horizontal='center', vertical='center')

    for emp in employees:
        entries = CycleTyreEntry.objects.filter(
            linked_employee_id=emp.id,
            date__year=target_year,
            date__month=target_month
        ).order_by('date')

        tyre_data = {}
        if entries.exists():
            for e in entries:
                t_name = re.sub(r'\s*\[.*?kg\]', '', str(e.tyre_item), flags=re.IGNORECASE).strip()
                if not t_name:
                    t_name = str(e.tyre_item)
                if t_name not in tyre_data:
                    tyre_data[t_name] = {d: {'A': 0, 'B': 0} for d in range(1, num_days + 1)}
                tyre_data[t_name][e.date.day]['A'] += (e.first_grade or 0)
                tyre_data[t_name][e.date.day]['B'] += (e.second_grade or 0)
        else:
            prods = Production.objects.filter(
                employee=emp,
                date__year=target_year,
                date__month=target_month
            ).order_by('date')
            for p in prods:
                t_name = re.sub(r'\s*\[.*?kg\]', '', p.product_name, flags=re.IGNORECASE).strip()
                if not t_name:
                    t_name = str(p.product_name)
                if t_name not in tyre_data:
                    tyre_data[t_name] = {d: {'A': 0, 'B': 0} for d in range(1, num_days + 1)}
                tyre_data[t_name][p.date.day]['A'] += int(p.quantity or 0)

        tyre_list = sorted(list(tyre_data.keys()))
        if not tyre_list:
            continue

        K = len(tyre_list)
        raw_name = re.sub(r'[\\/*?:\[\]]', '', emp.name).strip().upper()[:28] or f"EMP_{emp.id}"
        sheet_title = raw_name
        counter = 1
        while sheet_title in wb.sheetnames:
            sheet_title = f"{raw_name[:25]}_{counter}"
            counter += 1

        ws = wb.create_sheet(title=sheet_title)
        ws.views.sheetView[0].showGridLines = True

        # Row 1: Employee Name
        mid_col = max(2, (2 * K + 1) // 2)
        end_col = min(2 * K + 1, mid_col + 4)
        ws.merge_cells(start_row=1, start_column=mid_col, end_row=1, end_column=end_col)
        c_emp = ws.cell(1, mid_col, emp.name.upper())
        c_emp.font = font_title
        c_emp.alignment = align_center

        # Row 2: DATE and Tyre Names
        c_date = ws.cell(2, 1, 'DATE')
        c_date.font = font_header
        c_date.alignment = align_center
        c_date.border = thin_border

        for i, t_name in enumerate(tyre_list):
            c_a = 2 + 2 * i
            c_b = 3 + 2 * i
            ws.merge_cells(start_row=2, start_column=c_a, end_row=2, end_column=c_b)
            cell = ws.cell(2, c_a, t_name)
            cell.font = font_header
            cell.alignment = align_center
            cell.border = thin_border
            ws.cell(2, c_b).border = thin_border

        # Row 3: A and B
        ws.cell(3, 1).border = thin_border
        for i in range(K):
            c_a = 2 + 2 * i
            c_b = 3 + 2 * i
            ca = ws.cell(3, c_a, 'A')
            ca.font = font_sub
            ca.alignment = align_center
            ca.border = thin_border
            cb = ws.cell(3, c_b, 'B')
            cb.font = font_sub
            cb.alignment = align_center
            cb.border = thin_border

        # Rows 4 to (3 + num_days): Days 1 to num_days
        for d in range(1, num_days + 1):
            r = 3 + d
            c_d = ws.cell(r, 1, d)
            c_d.font = font_data
            c_d.alignment = align_center
            c_d.border = thin_border

            for i, t_name in enumerate(tyre_list):
                c_a = 2 + 2 * i
                c_b = 3 + 2 * i
                q_a = tyre_data[t_name][d]['A']
                q_b = tyre_data[t_name][d]['B']

                cell_a = ws.cell(r, c_a, q_a if q_a > 0 else None)
                cell_a.font = font_data
                cell_a.alignment = align_center
                cell_a.border = thin_border

                cell_b = ws.cell(r, c_b, q_b if q_b > 0 else None)
                cell_b.font = font_data
                cell_b.alignment = align_center
                cell_b.border = thin_border

        # Sum Row
        sum_row = 4 + num_days
        c_sum_lbl = ws.cell(sum_row, 1, '')
        c_sum_lbl.border = thin_border
        for c in range(2, 2 * K + 2):
            col_letter = get_column_letter(c)
            cell_sum = ws.cell(sum_row, c, f'=SUM({col_letter}4:{col_letter}{sum_row - 1})')
            cell_sum.font = font_data
            cell_sum.alignment = align_center
            cell_sum.border = thin_border

        # Repeat Tyre Name Row
        tyre_repeat_row = sum_row + 1
        for i, t_name in enumerate(tyre_list):
            c_a = 2 + 2 * i
            c_b = 3 + 2 * i
            ws.merge_cells(start_row=tyre_repeat_row, start_column=c_a, end_row=tyre_repeat_row, end_column=c_b)
            cell = ws.cell(tyre_repeat_row, c_a, t_name)
            cell.font = font_header
            cell.alignment = align_center
            cell.border = thin_border
            ws.cell(tyre_repeat_row, c_b).border = thin_border

        # Repeat A/B Row
        ab_repeat_row = tyre_repeat_row + 1
        for i in range(K):
            c_a = 2 + 2 * i
            c_b = 3 + 2 * i
            ca = ws.cell(ab_repeat_row, c_a, 'A')
            ca.font = font_sub
            ca.alignment = align_center
            ca.border = thin_border
            cb = ws.cell(ab_repeat_row, c_b, 'B')
            cb.font = font_sub
            cb.alignment = align_center
            cb.border = thin_border

        # PRODUCTION Row
        prod_row = ab_repeat_row + 1
        c_prod_lbl = ws.cell(prod_row, 1, 'PRODUCTION')
        c_prod_lbl.font = font_header
        c_prod_lbl.alignment = align_center
        c_prod_lbl.border = thin_border

        total_earning_col = 2 * K + 2
        c_te = ws.cell(prod_row, total_earning_col, 'TOTAL EARING')
        c_te.font = font_header
        c_te.alignment = align_center
        c_te.border = thin_border

        for i in range(K):
            c_a = 2 + 2 * i
            c_b = 3 + 2 * i
            col_a_let = get_column_letter(c_a)
            col_b_let = get_column_letter(c_b)
            ws.merge_cells(start_row=prod_row, start_column=c_a, end_row=prod_row, end_column=c_b)
            cell = ws.cell(prod_row, c_a, f'={col_a_let}{sum_row}+{col_b_let}{sum_row}')
            cell.font = font_total
            cell.alignment = align_center
            cell.border = thin_border
            ws.cell(prod_row, c_b).border = thin_border

        # RATE Row
        rate_row = prod_row + 1
        c_rate_lbl = ws.cell(rate_row, 1, 'RATE')
        c_rate_lbl.font = font_header
        c_rate_lbl.alignment = align_center
        c_rate_lbl.border = thin_border

        for i, t_name in enumerate(tyre_list):
            c_a = 2 + 2 * i
            c_b = 3 + 2 * i
            # Find rate in WorkerItemRate
            r_obj = WorkerItemRate.objects.filter(employee=emp, product_name__iexact=t_name).first()
            if not r_obj:
                r_obj = WorkerItemRate.objects.filter(employee=emp, product_name__icontains=t_name).first()
            if not r_obj:
                for wir in WorkerItemRate.objects.filter(employee=emp):
                    clean_wir = re.sub(r'\s*\[.*?kg\]', '', wir.product_name, flags=re.IGNORECASE).strip().lower()
                    clean_t = t_name.lower()
                    if clean_wir == clean_t or clean_wir in clean_t or clean_t in clean_wir:
                        r_obj = wir
                        break

            if not r_obj or not r_obj.rate:
                p_obj = Production.objects.filter(employee=emp, product_name__iexact=t_name).exclude(rate=0).first()
                if not p_obj:
                    p_obj = Production.objects.filter(employee=emp, product_name__icontains=t_name).exclude(rate=0).first()
                rate_val = float(p_obj.rate) if p_obj and p_obj.rate else 0.0
            else:
                rate_val = float(r_obj.rate)

            rate_100 = round(rate_val * 100, 2)
            ws.merge_cells(start_row=rate_row, start_column=c_a, end_row=rate_row, end_column=c_b)
            cell = ws.cell(rate_row, c_a, rate_100)
            cell.font = font_total
            cell.alignment = align_center
            cell.border = thin_border
            cell.number_format = '#,##0.00'
            ws.cell(rate_row, c_b).border = thin_border

        # TOTAL Row
        tot_row = rate_row + 1
        c_tot_lbl = ws.cell(tot_row, 1, 'TOTAL')
        c_tot_lbl.font = font_header
        c_tot_lbl.alignment = align_center
        c_tot_lbl.border = thin_border

        sum_formula_parts = []
        for i in range(K):
            c_a = 2 + 2 * i
            c_b = 3 + 2 * i
            col_let = get_column_letter(c_a)
            ws.merge_cells(start_row=tot_row, start_column=c_a, end_row=tot_row, end_column=c_b)
            cell = ws.cell(tot_row, c_a, f'={col_let}{rate_row}*{col_let}{prod_row}/100')
            cell.font = font_total
            cell.alignment = align_center
            cell.border = thin_border
            cell.number_format = '#,##0.00'
            ws.cell(tot_row, c_b).border = thin_border
            sum_formula_parts.append(f'{col_let}{tot_row}')

        te_col_let = get_column_letter(total_earning_col)
        cell_tot_earning = ws.cell(tot_row, total_earning_col, '=' + '+'.join(sum_formula_parts))
        cell_tot_earning.font = font_total
        cell_tot_earning.alignment = align_center
        cell_tot_earning.border = thin_border
        cell_tot_earning.number_format = '#,##0.00'

        # Incentive Block
        inc_row = tot_row + 5
        lbl_col_1 = max(2, 2 * K - 3)
        lbl_col_2 = lbl_col_1 + 1
        amt_col = total_earning_col - 1
        amt_col_let = get_column_letter(amt_col)

        ws.cell(inc_row, lbl_col_1, '15.62% FIX').font = font_header
        ws.cell(inc_row, lbl_col_2, 'INCENTIVE ').font = font_header
        c_inc = ws.cell(inc_row, amt_col, f'={te_col_let}{tot_row}*15.62%')
        c_inc.font = font_total
        c_inc.number_format = '#,##0.00'
        c_inc.alignment = align_center

        prod_earn_row = inc_row + 1
        ws.cell(prod_earn_row, lbl_col_2, 'TOTAL PRODUCTION EARING ').font = font_header
        c_pe = ws.cell(prod_earn_row, amt_col, f'={te_col_let}{tot_row}')
        c_pe.font = font_total
        c_pe.number_format = '#,##0.00'
        c_pe.alignment = align_center

        grand_row = prod_earn_row + 1
        ws.cell(grand_row, lbl_col_2, 'GRAND TOTAL').font = font_title
        c_gt = ws.cell(grand_row, amt_col, f'={amt_col_let}{prod_earn_row}+{amt_col_let}{inc_row}')
        c_gt.font = font_title
        c_gt.number_format = '#,##0.00'
        c_gt.alignment = align_center

        # Column dimensions
        ws.column_dimensions['A'].width = 16
        for c in range(2, 2 * K + 2):
            ws.column_dimensions[get_column_letter(c)].width = 14
        ws.column_dimensions[te_col_let].width = 18

    if len(wb.sheetnames) > 1 and default_sheet.title in wb.sheetnames:
        wb.remove(default_sheet)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"CY-TYRE_PRODUCTION_COMPANY_EMP_{target_year}_{target_month:02d}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
