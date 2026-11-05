from django.urls import path
from . import views

urlpatterns = [
    # Mixing Sheet (existing)
    path('mixing/', views.mixing_sheet_view, name='mixing-sheet'),
    path('mixing/<int:entry_id>/', views.delete_mixing_entry, name='delete-mixing-entry'),
    path('mixing/export-excel/', views.export_excel_view, name='export-mixing-excel'),

    # Tally Card / Stock Ledger
    path('groups/', views.material_group_list, name='material-group-list'),
    path('groups/<int:pk>/', views.material_group_detail, name='material-group-detail'),
    path('materials/', views.material_list, name='material-list'),
    path('materials/<int:pk>/', views.material_detail, name='material-detail'),
    path('materials/<int:pk>/passbook/', views.material_passbook_view, name='material-passbook'),
    path('materials/<int:pk>/passbook/export-excel/', views.material_passbook_excel, name='material-passbook-excel'),

    # Stock Entries
    path('stock-entries/', views.stock_entry_list, name='stock-entry-list'),
    path('stock-entries/bulk/', views.bulk_shift_entry, name='stock-entry-bulk'),
    path('stock-entries/<int:pk>/', views.stock_entry_detail, name='stock-entry-detail'),

    # Current Stock & Forecast
    path('current-stock/', views.current_stock_view, name='current-stock'),
    path('forecast/', views.stock_forecast_view, name='stock-forecast'),

    # Factory Format Daily Stock Sheet & Excel Export
    path('daily-sheet/', views.daily_stock_sheet_view, name='daily-stock-sheet'),
    path('daily-sheet/export-excel/', views.daily_stock_sheet_excel, name='daily-stock-sheet-excel'),
]
