from django.urls import path

from .views import InventoryItemListCreateView, StockAdjustView, WarehouseListCreateView

urlpatterns = [
    path("warehouses", WarehouseListCreateView.as_view(), name="warehouse-list"),
    path("items", InventoryItemListCreateView.as_view(), name="item-list"),
    path("items/<int:item_id>/stock", StockAdjustView.as_view(), name="item-stock"),
]
