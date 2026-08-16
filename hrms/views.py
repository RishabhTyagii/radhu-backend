import datetime
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
    Advance, Bonus, Deduction, Salary,
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


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def employee_detail(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    if request.method == "DELETE":
        emp.delete()
        return Response({"ok": True})
    elif request.method == "PUT":
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
            "absent_days": absent_days,
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
            if not emp_id:
                continue
            att_status = entry.get("status", "Present")
            wh = Decimal(str(entry.get("working_hours", 8)))
            ot = Decimal(str(entry.get("overtime_hours", 0)))
            remarks = entry.get("remarks", "").strip()

            Attendance.objects.update_or_create(
                employee_id=emp_id,
                date=date_val,
                defaults={
                    "status": att_status,
                    "working_hours": wh,
                    "overtime_hours": ot,
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
        serializer.save(created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def salary_list(request):
    today = datetime.date.today()

    if request.method == "POST":
        month = int(request.data.get("month", today.month))
        year = int(request.data.get("year", today.year))
        emp_id = request.data.get("employee")

        employees = Employee.objects.filter(status="Active")
        if emp_id:
            employees = employees.filter(pk=emp_id)

        _, days_in_month = monthrange(year, month)
        generated_salaries = []

        with transaction.atomic():
            for emp in employees:
                attendances = Attendance.objects.filter(
                    employee=emp, date__year=year, date__month=month
                )
                present_days = attendances.filter(status="Present").count()
                half_days = attendances.filter(status="Half Day").count()
                total_worked_days = Decimal(str(present_days)) + (Decimal(str(half_days)) * Decimal("0.5"))

                total_ot_hours = attendances.aggregate(tot=Sum("overtime_hours"))["tot"] or Decimal("0")
                overtime_amt = total_ot_hours * (emp.overtime_rate or Decimal("0"))

                if days_in_month > 0 and emp.basic_salary > 0:
                    per_day_salary = emp.basic_salary / Decimal(str(days_in_month))
                    earned_basic = per_day_salary * total_worked_days
                else:
                    earned_basic = Decimal("0")

                prod_amt = Production.objects.filter(
                    employee=emp, date__year=year, date__month=month
                ).aggregate(tot=Sum("total_amount"))["tot"] or Decimal("0")

                bonus_amt = Bonus.objects.filter(
                    employee=emp, date__year=year, date__month=month
                ).aggregate(tot=Sum("amount"))["tot"] or Decimal("0")

                adv_amt = Advance.objects.filter(
                    employee=emp, date__year=year, date__month=month
                ).aggregate(tot=Sum("amount"))["tot"] or Decimal("0")

                ded_amt = Deduction.objects.filter(
                    employee=emp, date__year=year, date__month=month
                ).aggregate(tot=Sum("amount"))["tot"] or Decimal("0")

                gross = earned_basic + prod_amt + overtime_amt
                pf_amt = (gross * (emp.pf_percent or Decimal("0"))) / Decimal("100")
                esi_amt = (gross * (emp.esi_percent or Decimal("0"))) / Decimal("100")

                net = (gross + bonus_amt) - (adv_amt + ded_amt + pf_amt + esi_amt)
                net = max(net, Decimal("0"))

                sal, created = Salary.objects.update_or_create(
                    employee=emp,
                    month=month,
                    year=year,
                    defaults={
                        "basic_salary": round(earned_basic, 2),
                        "overtime_amount": round(overtime_amt, 2),
                        "production_amount": round(prod_amt, 2),
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

    attendances = Attendance.objects.filter(employee=emp, date__year=sal.year, date__month=sal.month)
    present_days = attendances.filter(status="Present").count()
    half_days = attendances.filter(status="Half Day").count()
    absent_days = attendances.filter(status="Absent").count()

    return Response({
        "salary": SalarySerializer(sal).data,
        "employee": EmployeeSerializer(emp).data,
        "attendance_summary": {
            "days_in_month": days_in_month,
            "present_days": present_days,
            "half_days": half_days,
            "absent_days": absent_days,
            "total_worked_days": present_days + (half_days * 0.5),
        }
    })
