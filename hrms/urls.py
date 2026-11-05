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
    path("production/items/", views.production_items, name="hrms_production_items"),
    path("production/last-rate/", views.production_last_rate, name="hrms_production_last_rate"),
    path("production/<int:pk>/", views.production_detail, name="hrms_production_detail"),
    
    path("advance/", views.advance_list, name="hrms_advance_list"),
    path("advance/<int:pk>/", views.advance_detail, name="hrms_advance_detail"),
    
    path("bonus/", views.bonus_list, name="hrms_bonus_list"),
    path("bonus/<int:pk>/", views.bonus_detail, name="hrms_bonus_detail"),
    
    path("deduction/", views.deduction_list, name="hrms_deduction_list"),
    path("deduction/<int:pk>/", views.deduction_detail, name="hrms_deduction_detail"),
    
    path("salary/", views.salary_list, name="hrms_salary_list"),
    path("salary/<int:pk>/slip/", views.salary_slip, name="hrms_salary_slip"),
    path('attendance/monthly-register/', views.monthly_attendance_register, name="monthly_attendance_register"),
    path('attendance/monthly/', views.attendance_monthly_data, name="attendance_monthly_data"),
    path('attendance/bulk-any/', views.bulk_attendance_any, name="bulk_attendance_any"),
    path('employees/<int:pk>/leave-balance/', views.leave_balance_detail, name="hrms_leave_balance"),
    path('item-rates/', views.item_rates_list, name="hrms_item_rates_list"),
    path('item-rates/<int:pk>/', views.item_rate_detail, name="hrms_item_rate_detail"),
    path('avg-production/cycle-tyre/', views.avg_production_cycle_tyre, name="hrms_avg_production_cycle_tyre"),
    path('production/export-cycle-press-excel/', views.export_cycle_press_production_excel, name="hrms_export_cycle_press_production_excel"),
]
