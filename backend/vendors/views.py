from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import HasRole, VendorPermission
from config.pagination import StandardPagination
from .models import Vendor
from .serializers import VendorSerializer


class VendorViewSet(viewsets.ModelViewSet):
    """
    Admin              : full CRUD
    Dispatcher         : read-only (list + retrieve)
    Vendor             : read-only (list + retrieve own record)
    Driver / Anonymous : no access
    """

    queryset = Vendor.objects.all().order_by("-id")
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated, VendorPermission]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        role = getattr(user, "role", None)
        # Vendors only see their own record
        if role == "vendor":
            qs = qs.filter(user=user)
        return qs

    def create(self, request, *args, **kwargs):
        if getattr(request.user, "role", None) != "admin":
            return Response({"detail": "Only admins can create vendors"}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if getattr(request.user, "role", None) != "admin":
            return Response({"detail": "Only admins can update vendors"}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if getattr(request.user, "role", None) != "admin":
            return Response({"detail": "Only admins can update vendors"}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if getattr(request.user, "role", None) != "admin":
            return Response({"detail": "Only admins can delete vendors"}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], permission_classes=[HasRole("admin")])
    def link_user(self, request, pk=None):
        vendor = self.get_object()
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = get_object_or_404(User, id=user_id)
        vendor.user = user
        vendor.save()
        return Response(VendorSerializer(vendor).data)
