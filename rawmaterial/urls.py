from django.urls import path
from . import views

urlpatterns = [
    path('mixing/', views.mixing_sheet_view, name='mixing-sheet'),
    path('mixing/<int:entry_id>/', views.delete_mixing_entry, name='delete-mixing-entry'),
    path('mixing/export-excel/', views.export_excel_view, name='export-mixing-excel'),
]
