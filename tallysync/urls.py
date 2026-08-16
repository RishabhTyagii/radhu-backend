from django.urls import path
from . import views

urlpatterns = [
    path("webhook/", views.tally_webhook, name="tally_webhook"),
    path("sales/", views.sales_summary, name="tally_sales_summary"),
    path("invoice/<int:pk>/", views.invoice_detail, name="tally_invoice_detail"),
    path("mapping/", views.mapping_list, name="tally_mapping_list"),
    path("mapping/add/", views.add_mapping, name="tally_add_mapping"),
    path("mapping/<int:pk>/delete/", views.delete_mapping, name="tally_delete_mapping"),
    path("logs/", views.sync_log, name="tally_sync_log"),
    path("retry-pending/", views.retry_pending_now, name="tally_retry_pending"),
    path("pending/<int:pk>/retry/", views.retry_single_pending, name="tally_retry_single_pending"),
    path("pending/<int:pk>/map/", views.map_pending_item, name="tally_map_pending_item"),
    path("stock-items/", views.all_stock_items, name="tally_stock_items"),
]
