from django.urls import path

from .views import DashboardStatsView, DashboardSummaryView

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("stats", DashboardStatsView.as_view(), name="dashboard-stats"),
]
