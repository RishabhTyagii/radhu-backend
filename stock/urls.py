from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="api_dashboard"),
    path("tyres/", views.tyres_list, name="api_tyres_list"),
    path("tyres/create/", views.add_tyre, name="api_add_tyre"),
    path("production/", views.add_production, name="api_add_production"),
    path("production/recent/", views.recent_production, name="api_recent_production"),
    path("import-excel/", views.import_production_excel, name="api_import_excel"),
    path("dispatch/", views.add_dispatch, name="api_add_dispatch"),
    path("dispatch/recent/", views.recent_dispatch, name="api_recent_dispatch"),
    path("adjustment/", views.add_adjustment, name="api_add_adjustment"),
    path("entries/", views.entries_log, name="api_entries_log"),
    path("monthly-report/", views.monthly_report, name="api_monthly_report"),
    path("production-sheet/", views.production_sheet, name="api_production_sheet"),
    path("production-sheet/export/", views.production_sheet_export, name="api_production_sheet_export"),
    path("daily-summary/", views.daily_summary, name="api_daily_summary"),
]
