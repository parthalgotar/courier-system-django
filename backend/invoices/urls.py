from rest_framework.routers import SimpleRouter

from .views import CustomerViewSet, InvoiceViewSet, JournalViewSet, PaymentViewSet, TagViewSet

router = SimpleRouter(trailing_slash=True)
router.register("payments", PaymentViewSet, basename="payment")
router.register("journals", JournalViewSet, basename="journal")
router.register("customers", CustomerViewSet, basename="customer")
router.register("tags", TagViewSet, basename="tag")
router.register("", InvoiceViewSet, basename="invoice")

urlpatterns = router.urls
