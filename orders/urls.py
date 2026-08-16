from django.urls import path
from . import views

urlpatterns = [
    path("parties/", views.party_list, name="orders_party_list"),
    path("parties/<int:pk>/", views.party_detail, name="orders_party_detail"),
    path("catalog/", views.stock_catalog, name="orders_stock_catalog"),
    path("", views.order_list, name="orders_order_list"),
    path("<int:pk>/", views.order_detail, name="orders_order_detail"),
]
