from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import FleetPermission, HasRole
from config.pagination import StandardPagination
from .models import Driver, Vehicle
from .serializers import DriverLocationSerializer, DriverSerializer, VehicleSerializer


class DriverListCreateView(generics.ListCreateAPIView):
    """
    GET  /fleet/drivers — admin, dispatcher, driver (read-only; driver sees self only)
    POST /fleet/drivers — admin only
    """

    queryset = Driver.objects.all().order_by("-id")
    serializer_class = DriverSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Driver.objects.all().order_by("-id")
        user = self.request.user
        if getattr(user, "role", None) == "driver":
            return qs.filter(user=user)
        return qs

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasRole("admin")()]
        return [IsAuthenticated(), FleetPermission()]


class DriverLocationView(APIView):
    """
    PATCH /fleet/drivers/{id}/location
    Admin can update any driver. Dispatcher: read-only (no PATCH).
    Driver: can only update own location.
    """

    permission_classes = [HasRole("admin", "dispatcher", "driver")]

    def patch(self, request, driver_id):
        driver = get_object_or_404(Driver, id=driver_id)
        role = getattr(request.user, "role", None)
        if role == "dispatcher":
            return Response({"detail": "Dispatchers cannot update driver location"}, status=403)
        if role == "driver":
            if driver.user_id != request.user.id:
                return Response({"detail": "Drivers can only update their own location"}, status=403)

        serializer = DriverLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        driver.current_lat = serializer.validated_data["latitude"]
        driver.current_lng = serializer.validated_data["longitude"]
        driver.save()
        return Response(DriverSerializer(driver).data)


class VehicleListCreateView(generics.ListCreateAPIView):
    """
    GET  /fleet/vehicles — admin, dispatcher, driver (read-only)
    POST /fleet/vehicles — admin only
    """

    queryset = Vehicle.objects.all().order_by("-id")
    serializer_class = VehicleSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasRole("admin")()]
        return [IsAuthenticated(), FleetPermission()]
