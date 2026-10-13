from django.urls import path

from .views import DriverListCreateView, DriverLocationView, VehicleListCreateView

urlpatterns = [
    path("drivers", DriverListCreateView.as_view(), name="driver-list"),
    path("drivers/<int:driver_id>/location", DriverLocationView.as_view(), name="driver-location"),
    path("vehicles", VehicleListCreateView.as_view(), name="vehicle-list"),
]
