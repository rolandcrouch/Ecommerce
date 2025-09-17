from rest_framework.permissions import BasePermission

from shop.models import Product, Review, Store  # adjust import path as needed

class IsVendor(BasePermission):
    message = "Only vendors can access this endpoint."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and hasattr(user, "vendor"))

    def has_object_permission(self, request, view, obj):
        user_id = request.user.id
        if isinstance(obj, Review):
            return obj.product.store.owner_id == user_id
        if isinstance(obj, Product):
            return obj.store.owner_id == user_id
        if isinstance(obj, Store):
            return obj.owner_id == user_id
        return False