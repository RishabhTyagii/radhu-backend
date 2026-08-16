from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="cycletyres_dashboard"),
    path("add-item/", views.add_item, name="cycletyres_add_item"),
    path("production/", views.add_production, name="cycletyres_production"),
    path("import-excel/", views.import_production_excel, name="cycletyres_import_excel"),
    path("second-grade/", views.second_grade_stock, name="cycletyres_second_grade"),
    path("sale/", views.add_sale, name="cycletyres_sale"),
    path("adjustment/", views.add_adjustment, name="cycletyres_adjustment"),
    path("entries/", views.entries_log, name="cycletyres_entries"),
    path("monthly-report/", views.monthly_report, name="cycletyres_monthly_report"),
    path("daily-summary/", views.daily_summary, name="cycletyres_daily_summary"),
    path("production-sheet/", views.production_sheet, name="cycletyres_production_sheet"),
]
