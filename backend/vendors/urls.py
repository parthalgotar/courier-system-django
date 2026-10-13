from rest_framework.routers import DefaultRouter

from .views import VendorViewSet

router = DefaultRouter(trailing_slash=True)
router.register("", VendorViewSet, basename="vendor")

urlpatterns = router.urls
