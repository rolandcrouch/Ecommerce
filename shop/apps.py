import logging
from django.apps import AppConfig

log = logging.getLogger(__name__)

class ShopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Use the full Python path to the app package if it's nested:
    # name = "ecommerce.shop"
    name = "shop"

    def ready(self):
        # Register signal handlers here (no heavy side effects)
        try:
            from . import signals
        except Exception:
            log.exception("Failed to import shop.signals")
