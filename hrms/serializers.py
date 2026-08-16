from rest_framework import serializers
from .models import (
    Department, Employee, LeaveBalance, Attendance, Production,
    Advance, Bonus, Deduction, Salary,
)


class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = "__all__"

    def get_employee_count(self, obj):
        return obj.employee_set.count()


class EmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", default="", read_only=True)
    employee_type_display = serializers.CharField(source="get_employee_type_display", read_only=True)

    class Meta:
        model = Employee
        fields = "__all__"


class AttendanceSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    department_name = serializers.CharField(source="employee.department.name", default="", read_only=True)

    class Meta:
        model = Attendance
        fields = "__all__"


class ProductionSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model = Production
        fields = "__all__"


class AdvanceSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model = Advance
        fields = "__all__"


class BonusSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model = Bonus
        fields = "__all__"


class DeductionSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model = Deduction
        fields = "__all__"


class SalarySerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    employee_name = serializers.CharField(source="employee.name", read_only=True)
    department_name = serializers.CharField(source="employee.department.name", default="", read_only=True)

    class Meta:
        model = Salary
        fields = "__all__"
