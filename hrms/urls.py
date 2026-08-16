from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="hrms_dashboard"),
    
    path("departments/", views.department_list, name="hrms_department_list"),
    path("departments/<int:pk>/", views.department_detail, name="hrms_department_detail"),
    
    path("employees/", views.employee_list, name="hrms_employee_list"),
    path("employees/<int:pk>/", views.employee_detail, name="hrms_employee_detail"),
    
    path("attendance/", views.attendance_list, name="hrms_attendance_list"),
    path("attendance/bulk/", views.bulk_attendance, name="hrms_bulk_attendance"),
    
    path("production/", views.production_list, name="hrms_production_list"),
    path("production/<int:pk>/", views.production_detail, name="hrms_production_detail"),
    
    path("advance/", views.advance_list, name="hrms_advance_list"),
    path("advance/<int:pk>/", views.advance_detail, name="hrms_advance_detail"),
    
    path("bonus/", views.bonus_list, name="hrms_bonus_list"),
    path("bonus/<int:pk>/", views.bonus_detail, name="hrms_bonus_detail"),
    
    path("deduction/", views.deduction_list, name="hrms_deduction_list"),
    path("deduction/<int:pk>/", views.deduction_detail, name="hrms_deduction_detail"),
    
    path("salary/", views.salary_list, name="hrms_salary_list"),
    path("salary/<int:pk>/slip/", views.salary_slip, name="hrms_salary_slip"),
]
