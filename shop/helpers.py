from django.contrib.auth.models import User, Group
from .models import Profile, Product
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse_lazy
from django.conf import settings  


def _assign_role(user, role: str) -> None:
    """
    Assign a role to the user
    """
    vendors_group, _ = Group.objects.get_or_create(name="Vendors")
    if role == "vendor":
        user.groups.add(vendors_group)
    else:
        user.groups.remove(vendors_group)


def ensure_profile(user: User) -> Profile:
    """
    Get or create a Profile for the given user.
    """
    prof = getattr(user, "profile", None)
    if prof is None:
        prof, _ = Profile.objects.get_or_create(user=user)
    return prof


def _is_vendor(user: User) -> bool:
    """
    Return True if the user is considered a vendor 
    (role='vendor' OR in 'Vendors' group OR owns any stores).
    """
    if not user.is_authenticated:
        return False
    role_flag = getattr(user, "role", "") == "vendor"
    group_flag = user.groups.filter(name="Vendors").exists()
    owns_store = hasattr(user, "stores") and user.stores.exists()
    return role_flag or group_flag or owns_store


def _is_product_owner(user: User, product: Product) -> bool:
    """
    Return True if the user owns the store for this product.
    """
    store = getattr(product, "store", None)
    owner = getattr(store, "owner", None)
    return user.is_authenticated and (owner == user)


def _currency_symbol() -> str:
    """
    Get the configured currency symbol (default '$').
    """
    return getattr(settings, "CURRENCY_SYMBOL", "$")


vendor_required = user_passes_test(
    lambda u: u.is_authenticated and _is_vendor(u),
    login_url=reverse_lazy("login"),
)


def mark_user_has_purchased(user: User, products: list[Product] | None = None) -> None:
    """
    Mark a user as having purchased; optionally record specific products
    into Profile.purchased_products.
    """
    prof = ensure_profile(user)

    if not prof.has_purchased:
        prof.has_purchased = True
        prof.save(update_fields=["has_purchased"])

    if products:
        prof.purchased_products.add(*products)


def has_purchased_product(user: User, product: Product) -> bool:
    """
    Return True if the user has purchased this product.
    """
    prof = getattr(user, "profile", None)
    if not prof:
        return False
    return prof.purchased_products.filter(pk=product.pk).exists()