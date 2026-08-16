from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User

# Department
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# Employee
EMPLOYEE_TYPE = (
    ("Company", "Company"),
    ("Contractor", "Contractor"),
)

STATUS = (
    ("Active", "Active"),
    ("Inactive", "Inactive"),
)


class Employee(models.Model):
    employee_code = models.CharField(max_length=20, unique=True, db_index=True)
    photo = models.ImageField(upload_to="employees/", blank=True, null=True)
    name = models.CharField(max_length=150, db_index=True)
    father_name = models.CharField(max_length=150, blank=True)
    mobile = models.CharField(max_length=15)
    alternate_mobile = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    dob = models.DateField(null=True, blank=True)
    joining_date = models.DateField(null=True, blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, db_index=True
    )
    designation = models.CharField(max_length=100)
    employee_type = models.CharField(max_length=20, choices=EMPLOYEE_TYPE, default="Company")
    contractor_name = models.CharField(max_length=150, blank=True)
    address = models.TextField(blank=True)
    aadhaar = models.CharField(max_length=12, blank=True)
    pan = models.CharField(max_length=10, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc = models.CharField(max_length=20, blank=True)
    uan = models.CharField(max_length=30, blank=True)
    esi_number = models.CharField(max_length=30, blank=True)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pf_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    esi_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS, default="Active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["employee_code"]

    def __str__(self):
        return f"{self.employee_code} - {self.name}"


# Leave Balance
class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_balances")
    year = models.IntegerField()
    cl_balance = models.IntegerField(default=7)
    el_balance = models.IntegerField(default=13)

    class Meta:
        unique_together = ("employee", "year")
        ordering = ["-year"]

    def __str__(self):
        return f"{self.employee.name} - {self.year} | CL:{self.cl_balance} EL:{self.el_balance}"


# Attendance
ATTENDANCE_STATUS = (
    ("Present", "Present"),
    ("Absent", "Absent"),
    ("Half Day", "Half Day"),
    ("Holiday", "Holiday"),
    ("Week Off", "Week Off"),
)

LEAVE_TYPE = (
    ("", "---------"),
    ("CL", "CL (Casual Leave)"),
    ("EL", "EL (Earned Leave)"),
    ("LOP", "LOP (Loss of Pay)"),
)


class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_index=True)
    date = models.DateField(db_index=True)
    in_time = models.TimeField(blank=True, null=True)
    out_time = models.TimeField(blank=True, null=True)
    working_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS, default="Present")
    leave_type = models.CharField(max_length=10, choices=LEAVE_TYPE, blank=True)
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ("employee", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.employee.name} - {self.date} - {self.status}"


# Production (Piece-rate work)
class Production(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, db_index=True)
    date = models.DateField(db_index=True)
    product_name = models.CharField(max_length=150)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrms_productions")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.total_amount = Decimal(str(self.quantity)) * Decimal(str(self.rate))
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-date", "employee"]

    def __str__(self):
        return f"{self.employee.name} - {self.product_name} ({self.date})"


# Advance
class Advance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.employee.name} - Advance {self.amount}"


# Bonus
class Bonus(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.employee.name} - Bonus {self.amount}"


# Deduction
class Deduction(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.employee.name} - Deduction {self.amount}"


# Salary
class Salary(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    month = models.IntegerField()
    year = models.IntegerField()
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    production_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pf_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    esi_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    generated_on = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ("employee", "month", "year")
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.employee.name} - {self.month}/{self.year}"
