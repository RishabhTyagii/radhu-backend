from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="cycletube-dashboard"),
    path("add-item/", views.add_item, name="cycletube-add-item"),
    path("production/", views.add_production, name="cycletube-production"),
    path("sale/", views.add_sale, name="cycletube-sale"),
    path("adjustment/", views.add_adjustment, name="cycletube-adjustment"),
    path("entries/", views.entries_log, name="cycletube-entries"),
    path("monthly-report/", views.monthly_report, name="cycletube-monthly-report"),
    path("production-summary/", views.production_summary, name="cycletube-production-summary"),
    path("production-sheet/", views.production_sheet, name="cycletube-production-sheet"),
    path("export-production-sheet/", views.export_production_sheet, name="cycletube-export-production-sheet"),
    path("items/update-sku/", views.update_tube_sku, name="cycletube_update_sku"),
    path("transactions/", views.transactions_ledger, name="cycletube_transactions"),
]
