from django.urls import path
from . import views

urlpatterns = [
    path("daily/", views.daily_plant_performance, name="plant_performance_daily"),
    path("daily-log/", views.save_daily_manual_log, name="plant_performance_save_daily_log"),
    path("summary/", views.monthly_summary_rollup, name="plant_performance_summary"),
]
