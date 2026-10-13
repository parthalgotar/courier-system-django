from django.urls import path
from .views import NotificationListView, NotificationRetryView

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("<int:pk>/retry/", NotificationRetryView.as_view(), name="notification-retry"),
]
