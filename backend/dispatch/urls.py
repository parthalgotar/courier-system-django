from django.urls import path

from .views import AssignNearestDriverView

urlpatterns = [
    path("orders/<int:order_id>/assign", AssignNearestDriverView.as_view(), name="dispatch-assign"),
]
