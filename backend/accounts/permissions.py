from rest_framework.permissions import BasePermission, SAFE_METHODS


def _is_authenticated(user) -> bool:
    return bool(user and user.is_authenticated)


def HasRole(*roles):
    """Factory that returns a DRF permission class allowing only the given roles."""

    class _HasRole(BasePermission):
        def has_permission(self, request, view):
            user = request.user
            return bool(user and user.is_authenticated and user.role in roles)

    return _HasRole


# -----------------------------------------------------------------------xx---
# Accounting / Invoice Management
# --------------------------------------------------------------------------

class InvoicePermission(BasePermission):
    """Invoice access rules:

    ==========  ==================================================
    Admin       view / download all invoices, may modify
    Dispatcher  read-only access to all invoices
    Vendor      view / download (read-only) invoices of their OWN orders
    Driver      no invoice access at all
    ==========  ==================================================
    """

    allowed_roles = ("admin", "dispatcher", "vendor")

    def has_permission(self, request, view):
        user = request.user
        if not _is_authenticated(user):
            return False
        return getattr(user, "role", None) in self.allowed_roles

    def has_object_permission(self, request, view, obj):
        # `obj` is an Invoice.
        return self.user_can_access_order(request.user, obj.order, request.method)

    @staticmethod
    def user_can_access_order(user, order, method: str = "GET") -> bool:
        """Shared rule, also used by endpoints that start from an Order."""
        if not _is_authenticated(user):
            return False
        role = getattr(user, "role", None)
        if role == "admin" or getattr(user, "is_superuser", False):
            return True
        if role == "dispatcher":
            return method in SAFE_METHODS
        if role == "vendor":
            if method not in SAFE_METHODS or order is None:
                return False
            vendor_user_id = getattr(getattr(order, "vendor", None), "user_id", None)
            return vendor_user_id is not None and vendor_user_id == user.id
        return False  # driver, or any unknown role


# --------------------------------------------------------------------------
# Orders RBAC
# --------------------------------------------------------------------------    

class OrderPermission(BasePermission):
    """
    Admin / Dispatcher: full CRUD on any order.
    Vendor: read own orders + create own orders (enforced in get_queryset / create).
    Driver: read-only, own assigned orders only (enforced in get_queryset / has_object_permission).
    Anonymous: no access.
    """

    def has_permission(self, request, view):
        if not _is_authenticated(request.user):
            return False
        role = request.user.role
        if role in ("admin", "dispatcher"):
            return True
        if role == "vendor":
            return request.method in SAFE_METHODS or request.method == "POST"
        if role == "driver":
            return request.method in SAFE_METHODS
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        role = getattr(user, "role", None)
        if role == "admin":
            return True
        if role == "dispatcher":
            return request.method in SAFE_METHODS
        if role == "vendor":
            if request.method not in SAFE_METHODS:
                return False
            vendor_user_id = getattr(obj.vendor, "user_id", None)
            return vendor_user_id is not None and vendor_user_id == user.id
        if role == "driver":
            if request.method not in SAFE_METHODS:
                return False
            linked_driver = _get_linked_driver(user)
            if linked_driver is None:
                return False
            return obj.driver_id == linked_driver.pk
        return False


def _get_linked_driver(user):
    """Return the Driver record linked to this user, or None."""
    if not _is_authenticated(user):
        return None
    return getattr(user, "driver", None)


# --------------------------------------------------------------------------
# Vendors RBAC
# --------------------------------------------------------------------------

class VendorPermission(BasePermission):
    """
    Admin: full CRUD.
    Dispatcher: read-only (GET). Cannot create (POST) or delete vendors.
    Vendor: read-only. Object-level: only their own record.
    Driver / Anonymous: no access.
    """

    def has_permission(self, request, view):
        if not _is_authenticated(request.user):
            return False
        role = request.user.role
        if role == "admin":
            return True
        if role == "dispatcher":
            return request.method in SAFE_METHODS
        if role == "vendor":
            return request.method in SAFE_METHODS
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        role = getattr(user, "role", None)
        if role == "admin":
            return True
        if role == "dispatcher":
            return request.method in SAFE_METHODS
        if role == "vendor":
            if request.method not in SAFE_METHODS:
                return False
            return obj.user_id is not None and obj.user_id == user.id
        return False


# --------------------------------------------------------------------------
# Fleet / Drivers RBAC
# --------------------------------------------------------------------------

class FleetPermission(BasePermission):
    """
    Admin: full CRUD on drivers and vehicles.
    Dispatcher: read-only.
    Driver: read-only (own record only for drivers).
    Vendor / Anonymous: no access.
    """

    def has_permission(self, request, view):
        if not _is_authenticated(request.user):
            return False
        role = request.user.role
        if role == "admin":
            return True
        if role in ("dispatcher", "driver"):
            return request.method in SAFE_METHODS
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        role = getattr(user, "role", None)
        if role == "admin":
            return True
        if role == "dispatcher":
            return request.method in SAFE_METHODS
        if role == "driver":
            if request.method not in SAFE_METHODS:
                return False
            if hasattr(obj, "user_id"):
                return obj.user_id == user.id
            return True
        return False


# --------------------------------------------------------------------------
# Inventory RBAC
# --------------------------------------------------------------------------

class InventoryPermission(BasePermission):
    """
    Admin: full CRUD.
    Dispatcher: full CRUD (can manage inventory).
    Vendor: read-only.
    Driver / Anonymous: no access.
    """

    def has_permission(self, request, view):
        if not _is_authenticated(request.user):
            return False
        role = request.user.role
        if role in ("admin", "dispatcher"):
            return True
        if role == "vendor":
            return request.method in SAFE_METHODS
        return False


# --------------------------------------------------------------------------
# Dashboard RBAC
# --------------------------------------------------------------------------

class DashboardPermission(BasePermission):
    """
    Admin / Dispatcher: full dashboard (all orders).
    Vendor: dashboard scoped to own orders (enforced in view).
    Driver: dashboard scoped to own assigned orders (enforced in view).
    Anonymous: no access.
    """

    def has_permission(self, request, view):
        if not _is_authenticated(request.user):
            return False
        role = request.user.role
        return role in ("admin", "dispatcher", "vendor", "driver")


# --------------------------------------------------------------------------
# Dispatch RBAC
# --------------------------------------------------------------------------

class DispatchPermission(BasePermission):
    """
    Admin / Dispatcher: can assign drivers and plan routes.
    All others: no access.
    """

    def has_permission(self, request, view):
        if not _is_authenticated(request.user):
            return False
        role = request.user.role
        return role in ("admin", "dispatcher")
