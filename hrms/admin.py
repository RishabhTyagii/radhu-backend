from django.contrib import admin
from .models import (
    Department, Employee, LeaveBalance, Attendance, Production,
    Advance, Bonus, Deduction, Salary,
)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name",)

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "name", "department", "designation", "employee_type", "status", "mobile")
    search_fields = ("name", "employee_code", "mobile")
    list_filter = ("status", "employee_type", "department")

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "status", "working_hours", "overtime_hours")
    list_filter = ("status", "date")
    search_fields = ("employee__name", "employee__employee_code")

@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "product_name", "quantity", "rate", "total_amount")
    search_fields = ("employee__name", "product_name")

@admin.register(Advance)
class AdvanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "amount", "remarks")

@admin.register(Bonus)
class BonusAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "amount", "remarks")

@admin.register(Deduction)
class DeductionAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "amount", "remarks")

@admin.register(Salary)
class SalaryAdmin(admin.ModelAdmin):
    list_display = ("employee", "month", "year", "basic_salary", "production_amount", "overtime_amount", "net_salary")
    list_filter = ("year", "month")
