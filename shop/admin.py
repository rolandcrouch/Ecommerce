from django.contrib import admin
from .models import Store, Product

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__username")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "store", "price", "created_at")
    list_filter = ("store",)
    search_fields = ("name", "store__name")

