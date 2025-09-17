
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers


from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.text import slugify
from rest_framework import serializers

User = get_user_model()


class Vendor(models.Model):
    """
    Represents a seller account linked to a User. Vendors have a store name
    and optional bio, and can own multiple products.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    vendor_name = models.CharField(max_length=255)
    bio = models.TextField(blank=True)

    def __str__(self):
        return self.store_name
    

class Profile(models.Model):
    """
    Customer profile linked to a User.
    Tracks whether the user has purchased and which products they've bought.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    has_purchased = models.BooleanField(default=False)
    purchased_products = models.ManyToManyField(
        "shop.Product", blank=True, related_name="purchased_by"
    )

    def __str__(self):
        return f"Profile({self.user.username})"


class Store(models.Model):
    """
    A store owned by a User. Each owner can have multiple stores.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stores"
    )
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True)
    slug = models.SlugField(max_length=220, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Store name is unique per owner (as in your original code)
        unique_together = ("owner", "name")
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f"{self.owner_id}-{slugify(self.name)}"[:220]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    A product listed for sale in a given store.
    """
    store = models.ForeignKey(
        "shop.Store", on_delete=models.CASCADE, related_name="products",
        null=True, blank=True
    )
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Order(models.Model):
    """
    Represents a customer order. Tied to a User and includes timestamp
    and payment status.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)


class OrderItem(models.Model):
    """
    Represents a specific product within an order, including quantity.
    Links to both the Order and Product.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)


class Review(models.Model):
    """
    Represents a product review submitted by a user. Includes a rating
    (1–5), optional comment, and creation timestamp.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating})"
    

class ResetToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reset_tokens")
    token_hash = models.CharField(max_length=64, db_index=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "expires_at"]),
        ]

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_used(self) -> bool:
        return self.used_at is not None



# ----------------- Serializers (annotated only) -----------------

class StoreSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating stores. Owner is supplied from the request user.
    """
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Store
        fields = ["id", "owner", "name", "bio", "slug"]
        read_only_fields = ["id", "slug"]


class ProductSerializer(serializers.ModelSerializer):
    """
    Read/write serializer for products. By default `store` is read-only here
    and should be set by the view (e.g., taken from the URL).
    """
    class Meta:
        model = Product
        fields = ["id", "store", "name", "description", "price", 
                  "image", "stock", "created_at"]
        read_only_fields = ["id", "store", "created_at"]

    def validate_price(self, v):
        if v < 0:
            raise serializers.ValidationError("Price must be ≥ 0.")
        return v

    def validate_stock(self, v):
        if v < 0:
            raise serializers.ValidationError("Stock must be ≥ 0.")
        return v
    

class ReviewSerializer(serializers.ModelSerializer):
    """
    Public serializer for reviews; exposes username and product as PK.
    """
    user = serializers.CharField(source="user.username", read_only=True)
    product = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Review
        fields = ["id", "product", "user", "rating", "comment", "created_at"]


class StorePublicSerializer(serializers.ModelSerializer):
    """
    Public view of a store; includes minimal vendor info derived via owner.
    """
    vendor = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ["id", "name", "bio", "slug", "created_at", "vendor"] 

    def get_vendor(self, obj):
        try:
            v = obj.owner.vendor
            return {"id": v.id, "vendor_name": v.vendor_name}
        except Vendor.DoesNotExist:
            return {"id": None, "vendor_name": obj.owner.username}


class ProductPublicSerializer(serializers.ModelSerializer):
    """
    Public view of a product with a flat `store` reference (id only).
    """
    store = serializers.IntegerField(source="store_id", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "store", "name", "description", "price", 
                  "image", "stock", "created_at"]