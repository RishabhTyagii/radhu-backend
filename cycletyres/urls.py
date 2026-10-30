from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="cycletyres_dashboard"),
    path("add-item/", views.add_item, name="cycletyres_add_item"),
    path("production/", views.add_production, name="cycletyres_production"),
    path("production/<int:pk>/employee/", views.update_employee, name="cycletyres_update_employee"),
    path("import-excel/", views.import_production_excel, name="cycletyres_import_excel"),
    path("second-grade/", views.second_grade_stock, name="cycletyres_second_grade"),
    path("sale/", views.add_sale, name="cycletyres_sale"),
    path("adjustment/", views.add_adjustment, name="cycletyres_adjustment"),
    path("entries/", views.entries_log, name="cycletyres_entries"),
    path("monthly-report/", views.monthly_report, name="cycletyres_monthly_report"),
    path("ai-analytics/", views.ai_analytics, name="cycletyres_ai_analytics"),
    path("daily-summary/", views.daily_summary, name="cycletyres_daily_summary"),
    path("production-sheet/", views.production_sheet, name="cycletyres_production_sheet"),
    path("export-production-sheet/", views.export_production_sheet, name="cycletyres_export_production_sheet"),
    path("party-analytics/<int:party_id>/", views.party_analytics, name="cycletyres_party_analytics"),
    path("item-analytics/<int:item_id>/", views.item_analytics, name="cycletyres_item_analytics"),
    path("ai-analytics-v2/", views.ai_analytics_v2, name="cycletyres_ai_analytics_v2"),
    path("passbook/", views.passbook_ledger, name="cycletyres_passbook"),
    path("items/update-sku/", views.update_item_sku, name="cycletyres_update_sku"),
    path("transactions/", views.passbook_ledger, name="cycletyres_transactions"),
]

