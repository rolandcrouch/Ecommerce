from decimal import Decimal
from django.conf import settings
from .models import Product


BASKET_SESSION_ID = getattr(settings, "BASKET_SESSION_ID", "basket")

class Basket:
    """
    Handles shopping basket logic stored in the session. Supports adding,
    removing, and iterating over items, as well as calculating totals.
    """
    def __init__(self, request):
        self.session = request.session
        basket = self.session.get(BASKET_SESSION_ID)
        if basket is None:
            basket = {}
            self.session[BASKET_SESSION_ID] = basket
        self.basket = basket

    def add(self, product, quantity=1, update_quantity=False):
        product_id = str(product.id)

        if product_id not in self.basket:
            self.basket[product_id] = {'quantity': 0, 'price': str(product.price)}

        if update_quantity:
            self.basket[product_id]['quantity'] = quantity
        else:
            self.basket[product_id]['quantity'] += quantity

        self._commit()

    def _commit(self):
        self.session[BASKET_SESSION_ID] = self.basket
        self.session.modified = True

    def save(self):
        self._commit()

    def remove(self, product):
        product_id = str(product.id)
        if product_id in self.basket:
            del self.basket[product_id]
            self._commit()

    def __iter__(self):
        product_ids = self.basket.keys()
        products = Product.objects.filter(id__in=product_ids)

        for product in products:
            item = self.basket[str(product.id)].copy() 
            item['product'] = product
            item['total_price'] = Decimal(item['price']) * item['quantity']
            yield item

    def __len__(self):
        return sum(item['quantity'] for item in self.basket.values())

    def get_total_price(self):
        return sum(Decimal(item['price']) * item['quantity'] for item in self.basket.values())

    def clear(self):
        self.session.pop(BASKET_SESSION_ID, None) 
        self.session.modified = True