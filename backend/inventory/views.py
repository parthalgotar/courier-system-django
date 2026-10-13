from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasRole, InventoryPermission
from config.pagination import StandardPagination
from .models import InventoryItem, Warehouse
from .serializers import InventoryItemSerializer, StockAdjustSerializer, WarehouseSerializer


class WarehouseListCreateView(generics.ListCreateAPIView):
    """
    GET  /inventory/warehouses — admin, dispatcher, vendor (read-only)
    POST /inventory/warehouses — admin only
    """

    queryset = Warehouse.objects.all().order_by("-id")
    serializer_class = WarehouseSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasRole("admin")()]
        return [IsAuthenticated(), InventoryPermission()]


class InventoryItemListCreateView(generics.ListCreateAPIView):
    """
    GET  /inventory/items — admin, dispatcher, vendor (read-only)
    POST /inventory/items — admin, dispatcher
    """

    queryset = InventoryItem.objects.all().order_by("-id")
    serializer_class = InventoryItemSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasRole("admin", "dispatcher")()]
        return [IsAuthenticated(), InventoryPermission()]


class StockAdjustView(APIView):
    """
    PATCH /inventory/items/{id}/adjust — admin, dispatcher only
    """

    permission_classes = [HasRole("admin", "dispatcher")]

    def patch(self, request, item_id):
        item = get_object_or_404(InventoryItem, id=item_id)
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_qty = item.quantity + serializer.validated_data["delta"]
        if new_qty < 0:
            return Response({"detail": "Insufficient stock"}, status=status.HTTP_400_BAD_REQUEST)
        item.quantity = new_qty
        item.save()
        return Response(InventoryItemSerializer(item).data)
