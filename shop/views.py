
from datetime import timedelta
import hashlib
import secrets
import logging
log = logging.getLogger(__name__)
from typing import Any, Dict
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    parser_classes
)
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import SetPasswordForm
from django.core.mail import send_mail, EmailMultiAlternatives
from django.db import transaction
from django.db.models import Avg, Count
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import strip_tags, format_html

from django.views.generic.edit import FormView


from .functions.tweet import TwitterAPI
from .permissions import IsVendor
from .basket import Basket
from .forms import (
    CustomerRegisterForm,
    VendorRegisterForm,
    StoreForm,
    ProductForm,
    ReviewForm,
    ForgotUsernameForm,
    PasswordResetRequestForm,
)
from .models import Vendor, Product, ResetToken, Store, StoreSerializer, \
                    ProductSerializer, Review, ReviewSerializer,\
                    StorePublicSerializer, ProductPublicSerializer
from .utils import create_reset_token, build_reset_url, \
                        validate_and_consume_token, lookup_reset_token, \
                        consume_reset_token
from .helpers import mark_user_has_purchased, has_purchased_product, \
                    _assign_role, _is_vendor , _is_product_owner, \
                    _currency_symbol, vendor_required


# ---------- entry / registration ----------

@login_required
def post_login(request: HttpRequest) -> HttpResponse:
    """
    Redirect user after login: 
    vendors to store list, others to product list.
    """
    user = request.user
    if _is_vendor(user):
        return redirect("vendor_store_list")
    return redirect("product_list")


def register_customer(request: HttpRequest) -> HttpResponse:
    """
    Register a customer account and redirect to login.
    """
    if request.method == "POST":
        form = CustomerRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            _assign_role(user, "customer")
            messages.success(request, "Account created. " \
                                "You can now log in.")
            return redirect("login")
        messages.error(request, "Please fix the errors below.")
    else:
        form = CustomerRegisterForm()

    return render(request, "shop/register.html", {"form": form,
                                                   "role": "customer"})



@transaction.atomic
def register_vendor(request: HttpRequest) -> HttpResponse:
    """
    Register a vendor user and create their first store.
    """
    if request.method == "POST":
        form = VendorRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            vendor_name = form.cleaned_data.get("vendor_name")\
                        or f"{user.username}'s Store"
            bio = form.cleaned_data.get("bio", "")
            Vendor.objects.create(user=user, vendor_name=vendor_name, 
                                  bio=bio)
            _assign_role(user, "vendor")
            login(request, user)
            messages.success(request, "Your store was created.")
            return redirect("vendor_store_list")
        print("Register form errors:", form.errors)
    else:
        form = VendorRegisterForm()
    return render(request, "shop/register.html", 
                  {"form": form, "role": "vendor"})


# ---------- catalog & product detail ----------

def product_list(request: HttpRequest) -> HttpResponse:
    """
    Display all products to customers.
    """
    products = Product.objects.all()
    return render(request, "shop/product_list.html", 
                  {"products": products})


def product_detail(request: HttpRequest, product_id: int) \
                -> HttpResponse:
    """
    Show a single product, its reviews, and handle review submission.
    """
    product = get_object_or_404(Product, id=product_id)
    
    reviews_qs = product.reviews.select_related("user"). \
                            all().order_by("-created_at")
    reviews = list(reviews_qs)

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            return redirect("product_detail", product_id=product.id)
    else:
        form = ReviewForm()

    for r in reviews:
        r.is_verified = has_purchased_product(r.user, product)

    context = {
        "product": product,
        "reviews": reviews,
        "form": form,
        "user_is_vendor": _is_vendor(request.user),
        "user_is_owner": _is_product_owner(request.user, product),
    }
    return render(request, "shop/product_detail.html", context)


# ---------- vendor: products & stores ----------

@login_required
@vendor_required
def product_edit(request: HttpRequest, store_pk: int, pk: int) \
                                    -> HttpResponse:
    """
    Edit an existing product belonging to the current vendor.
    """
    store = get_object_or_404(Store, pk=store_pk, owner=request.user)
    product = get_object_or_404(Product, pk=pk, store=store)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, 
                           instance=product)
        if form.is_valid():
            obj = form.save(commit=False)

            if request.POST.get("remove_image"):
                if obj.image:
                    obj.image.delete(save=False)
                obj.image = None

            obj.save()
            if hasattr(form, "save_m2m"):
                form.save_m2m()

            messages.success(request, "Product updated.")
            return redirect("store_products", pk=store.pk)

        messages.error(request, "Please fix the errors below.")
    else:
        form = ProductForm(instance=product)

    return render(
        request,
        "shop/product_form.html",
        {"form": form, "store": store, "product": product},
    )


@login_required
def basket_detail(request: HttpRequest) -> HttpResponse:
    """
    Display the current user's basket contents.
    """
    basket = Basket(request)
    return render(request, "shop/basket_detail.html", {"basket": basket})


@login_required
def add_to_basket(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    Add a product to the basket (blocked for vendors/owners).
    """
    product = get_object_or_404(Product, id=product_id)

    if _is_vendor(request.user) or \
            _is_product_owner(request.user, product):
        messages.error(request, 
                        "Vendors and store owners cannot " \
                        "add items to the basket.")
        return redirect("product_detail", product_id=product.id)

    if request.method == "POST":
        basket = Basket(request)
        basket.add(product=product, quantity=1)
        messages.success(request, f"Added {product.name} \
                         to your basket.")
        return redirect("basket_detail")

    return redirect("product_detail", product_id=product.id)


@login_required
def remove_from_basket(request: HttpRequest, product_id: int) \
                                        -> HttpResponse:
    """
    Remove a product from the basket.
    """
    product = get_object_or_404(Product, id=product_id)
    basket = Basket(request)
    basket.remove(product)
    return redirect("basket_detail")


@login_required
def checkout(request: HttpRequest) -> HttpResponse:
    """
    Email an invoice for the current basket to the logged-in user,
    then clear the basket and mark the user as having purchased.
    """
    basket = Basket(request)

    # Block vendors
    if _is_vendor(request.user):
        messages.error(request, "Vendors cannot checkout.")
        return redirect("basket_detail")

    if request.method != "POST":
        return redirect("basket_detail")

    if len(basket) == 0:
        messages.error(request, "Your basket is empty.")
        return redirect("basket_detail")

    if not request.user.email:
        messages.error(request, "Your account has no email address. Please add one to receive the invoice.")
        return redirect("basket_detail")

    now = timezone.now()
    invoice_no = f"INV-{now.strftime('%Y%m%d%H%M%S')}-{request.user.id}"
    items = list(basket)              
    total = basket.get_total_price()

    context = {
        "user": request.user,
        "items": items,
        "total": total,
        "invoice_no": invoice_no,
        "generated_at": now,
        "site_name": getattr(settings, "SITE_NAME", "eCommerce"),
        "currency": _currency_symbol(),
    }

    html_body = render_to_string("shop/emails/invoice.html", context)
    text_body = strip_tags(html_body)
    subject = f"Your invoice {invoice_no}"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    to_email = [request.user.email]

    email = EmailMultiAlternatives(subject, text_body, from_email, to_email)
    email.attach_alternative(html_body, "text/html")
    email.send()

    purchased = [it["product"] for it in items]
    mark_user_has_purchased(request.user, products=purchased)

    basket.clear()

    messages.success(request, f"Invoice {invoice_no} sent to {request.user.email}.")
    return redirect("product_list")


# ---------- account utilities ----------

def forgot_username(request: HttpRequest) -> HttpResponse:
    """
    Email any usernames associated with the provided address.
    """
    message = ""
    if request.method == "POST":
        form = ForgotUsernameForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            users = User.objects.filter(email=email)
            if users.exists():
                username_list = ", ".join(u.username for u in users)
                send_mail(
                    "Your Username",
                    f"Your username(s): {username_list}",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                )
                message = "Username sent to your email."
            else:
                message = "No account with that email."
    else:
        form = ForgotUsernameForm()
    return render(request, "registration/forgot_username.html", 
                  {"form": form, "message": message})


def send_password_reset(request):
    """
    Neutral response to prevent user enumeration.
    """
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            user = getattr(form, "user", None)  # your form should attach user if found
            if user and user.email:
                raw = create_reset_token(user)
                reset_url = build_reset_url(request, raw)

                subject = "Password Reset Request"
                text_body = f"Click the link below to reset your password:\n{reset_url}"
                from_email = settings.DEFAULT_FROM_EMAIL
                to = [user.email]

                email = EmailMultiAlternatives(subject, text_body, from_email, to)
                # (Optional) Add HTML template:
                # html_body = render_to_string("registration/reset_email.html", {"reset_url": reset_url, "user": user})
                # email.attach_alternative(html_body, "text/html")
                email.send()

            messages.success(request, "If that account exists, a reset link has been sent.")
            return redirect("login")
        messages.error(request, "Please correct the errors below.")
    return render(request, "registration/request_password_reset.html", {"form": form})



def reset_user_password(request, token: str):
    """
    GET: validate token and show form (no consumption).
    POST: on valid form, set password and consume token.
    """
    user, rt = lookup_reset_token(token)
    if not user:
        return render(
            request,
            "registration/password_reset_confirm.html",
            {"validlink": False},
        )

    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                # consume only AFTER successfully setting the password
                consume_reset_token(rt)
            messages.success(request, "Your password has been reset. Please log in.")
            return redirect("login")
    else:
        form = SetPasswordForm(user)

    return render(
        request,
        "registration/reset_password_confirm_page.html",
        {"validlink": True, "form": form},
    )


# ---------- vendor: stores & product CRUD ----------

@login_required
@vendor_required
def vendor_store_list(request: HttpRequest) -> HttpResponse:
    """
    List all stores owned by the current vendor.
    """
    stores = Store.objects.filter(owner=request.user)
    return render(request, "shop/vendor_store_list.html", {"stores": stores})


@login_required
@vendor_required
def store_add(request):
    """
    Create a new store for the current vendor and (optionally) tweet it via X.
    """
    if request.method == "POST":
        form = StoreForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                store = form.save(commit=False)
                store.owner = request.user
                store.save()
                if hasattr(form, "save_m2m"):
                    form.save_m2m()

            # Build tweet text (trim bio a bit)
            bio = (store.bio or "")[:240]
            tweet_text = f"New store open on Ecommerce!\n{store.name}\n\n{bio}"

            # After-auth landing page
            next_after_auth = request.build_absolute_uri(reverse("vendor_store_list"))

            if settings.TWITTER_ENABLED:
                try:
                    api = TwitterAPI()  # loads token if present
                    if not getattr(api, "token", None):
                        connect_url = f"{reverse('twitter_start_auth')}?next={next_after_auth}"
                        messages.info(
                            request,
                            format_html(
                                f'Twitter isn’t connected yet. '
                                f'<a href="{connect_url}">Connect now</a> to auto-post.'
                            ),
                        )
                        return redirect("vendor_store_list")

                    # Optional media: try store.logo then store.image if you have those fields
                    media_ids = None
                    store_image = getattr(store, "logo", None) or getattr(store, "image", None)
                    if store_image:
                        try:
                            media_ids = [api.upload_media(store_image)]
                        except Exception:
                            log.exception("Twitter media upload failed for store_add")
                            messages.warning(request, "Couldn’t attach image; posting text only.")

                    try:
                        api.post_tweet(tweet_text, media_ids=media_ids)
                        messages.success(request, "Store announcement posted to X.")
                    except Exception as exc:
                        msg = str(exc)
                        if ("unauthorized_client" in msg
                                or "Missing valid authorization header" in msg):
                            reconnect_url = f"{reverse('twitter_start_auth')}?next={next_after_auth}"
                            messages.warning(
                                request,
                                format_html(
                                    f"Twitter session expired. "
                                    f'<a href="{reconnect_url}">Reconnect</a> to post future announcements.'
                                ),
                            )
                        elif "403" in msg or "Forbidden" in msg:
                            log.error("Twitter 403 on store_add: %s", msg)
                            messages.warning(
                                request,
                                "Twitter refused the request. Ensure app has Write + media.write scopes and re-authorize."
                            )
                        else:
                            log.exception("Twitter tweet failed on store_add: %s", msg)
                except Exception:
                    log.exception("Twitter integration error on store_add")

            return redirect("vendor_store_list")
    else:
        form = StoreForm()

    return render(request, "shop/store_form.html", {"form": form})


@login_required
@vendor_required
def store_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Edit an existing store owned by the current vendor.
    """
    store = get_object_or_404(Store, pk=pk, owner=request.user)

    if request.method == "POST":
        form = StoreForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, "Store updated.")
            return redirect("vendor_store_list")
        messages.error(request, "Please fix the errors below.")
    else:
        form = StoreForm(instance=store)

    return render(request, "shop/store_edit.html", {"form": form, 
                                                    "store": store})


@login_required
@vendor_required
def store_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Delete a store owned by the current vendor.
    """
    store = get_object_or_404(Store, pk=pk, owner=request.user)

    if request.method == "POST":
        store.delete()
        messages.success(request, "Store removed.")
        return redirect("vendor_store_list")

    return render(request, "shop/store_confirm_delete.html", {"store": store})


@login_required
@vendor_required
def store_products(request: HttpRequest, pk: int) -> HttpResponse:
    """
    List products for a specific store owned by the current vendor.
    """
    store = get_object_or_404(Store, pk=pk, owner=request.user)
    products = store.products.all()
    return render(request, "shop/store_product_list.html", 
                  {"store": store, "products": products})


@login_required
@vendor_required
def product_add(request, store_pk: int):
    store = get_object_or_404(Store, pk=store_pk, owner=request.user)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                product = form.save(commit=False)
                product.store = store
                product.save()
                if hasattr(form, "save_m2m"):
                    form.save_m2m()

            # Build tweet text
            desc = (product.description or "")[:240]
            tweet_text = (
                f"New product launched!\n"
                f"{product.name} is available now from {product.store.name}\n\n"
                f"{desc}"
            )

            # Where to send the user after connect/reconnect
            next_after_auth = request.build_absolute_uri(
                reverse("store_products", args=[store.pk])
            )

            if settings.TWITTER_ENABLED:
                try:
                    api = TwitterAPI()  # OAuth2 mode; will load token if present

                    # If not connected yet, nudge vendor to connect (no crash)
                    if not getattr(api, "token", None):
                        connect_url = f"{reverse('twitter_start_auth')}?next={next_after_auth}"
                        messages.info(
                            request,
                            format_html(
                                f'Twitter isn’t connected yet. '
                                f'<a href="{connect_url}">Connect now</a> to auto-post.'
                            ),
                        )
                        return redirect("store_products", pk=store.pk)

                    # Optional media upload
                    media_ids = None
                    if getattr(product, "image", None):
                        try:
                            media_ids = [api.upload_media(product.image)]
                        except Exception as exc:
                            log.exception("Twitter media upload failed")
                            messages.warning(
                                request,
                                "Couldn’t attach image to the tweet; posting text only."
                            )

                    # Post the tweet
                    try:
                        api.post_tweet(tweet_text, media_ids=media_ids)
                        messages.success(request, "Product tweeted to X successfully.")
                    except Exception as exc:
                        msg = str(exc)
                        # Token expired or refresh needs client auth, etc.
                        if ("unauthorized_client" in msg
                                or "Missing valid authorization header" in msg):
                            connect_url = f"{reverse('twitter_start_auth')}?next={next_after_auth}"
                            messages.warning(
                                request,
                                format_html(
                                    f"Twitter session expired. "
                                    f'<a href="{connect_url}">Reconnect</a> to post future products.'
                                ),
                            )
                        elif "403" in msg or "Forbidden" in msg:
                            # Often: missing write/media.write scope or app perms
                            log.error("Twitter 403 Forbidden: %s", msg)
                            messages.warning(
                                request,
                                "Twitter refused the request. "
                                "Ensure the app has Write + media.write scopes and re-authorize."
                            )
                        else:
                            log.exception("Twitter tweet failed: %s", msg)

                except Exception:
                    log.exception("Twitter integration error")

            return redirect("store_products", pk=store.pk)
    else:
        form = ProductForm()

    return render(request, "shop/product_form.html", {"form": form, "store": store})


@login_required
@vendor_required
def product_delete(request: HttpRequest, store_pk: int, pk: int) \
                                                -> HttpResponse:
    """
    Delete a product from the given store (owned by the current vendor).
    """
    product = get_object_or_404(Product, pk=pk, store__pk=store_pk, 
                                store__owner=request.user)
    if request.method == "POST":
        try:
            product.delete()
            messages.success(request, "Product deleted.")
        except ProtectedError:
            messages.error(request, "Cannot delete product because it "
                                "is referenced by other records.")
        return redirect("store_products", pk=store_pk)
    return render(request, "shop/product_confirm_delete.html", 
                  {"product": product, "store_pk": store_pk})


# ---------- API ----------

@api_view(['GET'])
def view_stores(request):
    if request.method == "GET":
        serializer = StoreSerializer(Store.objects.all(), many=True)
        return JsonResponse(data=serializer.data, safe=False)
    

@api_view(['POST'])
@authentication_classes([BasicAuthentication])
@permission_classes([IsVendor])
def add_store(request):
    serializer = StoreSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    try:
        with transaction.atomic():
            store = serializer.save()  
    except IntegrityError:
        return Response(
            {"detail": "You already have a store with this name."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(StoreSerializer(store).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsVendor])
@parser_classes([JSONParser, MultiPartParser, FormParser]) 
def add_product(request, store_id):
    store = get_object_or_404(Store, id=store_id, owner=request.user)

    serializer = ProductSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    product = serializer.save(store=store)
    return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_products(request, store_id):
    store = get_object_or_404(Store, id=store_id, owner=request.user)
    qs = store.products.all().order_by("name")
    return Response(ProductSerializer(qs, many=True).data)


def _paginator(request, default_size=20, max_size=100):
    p = PageNumberPagination()
    try:
        p.page_size = min(int(request.query_params.get("page_size", default_size)), max_size)
    except ValueError:
        p.page_size = default_size
    return p


@api_view(["GET"])
@permission_classes([IsVendor])  
def my_product_reviews(request):
    """
    All reviews across products in stores owned by the current user.
    Optional filters: ?store=<id>&product=<id>&rating=<1-5>
    """
    qs = Review.objects.filter(product__store__owner=request.user)

    store_id = request.query_params.get("store")
    if store_id:
        qs = qs.filter(product__store_id=store_id)

    product_id = request.query_params.get("product")
    if product_id:
        qs = qs.filter(product_id=product_id)

    rating = request.query_params.get("rating")
    if rating:
        try:
            qs = qs.filter(rating=int(rating))
        except (TypeError, ValueError):
            pass

    qs = qs.select_related("user", "product").order_by("-created_at")
    summary = qs.aggregate(count=Count("id"), avg_rating=Avg("rating"))

    paginator = _paginator(request)
    page = paginator.paginate_queryset(qs, request)
    data = ReviewSerializer(page, many=True).data

    response = paginator.get_paginated_response(data)
    response.data["summary"] = summary
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def vendor_stores(request):  # ← no vendor_id here
    """
    List stores and vendors.
    """
    qs = Store.objects.select_related("owner__vendor").order_by("name")

    vendor_id = request.query_params.get("vendor")  # optional filter
    if vendor_id:
        qs = qs.filter(owner__vendor__id=vendor_id)

    paginator = _paginator(request)
    page = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(
        StorePublicSerializer(page, many=True).data
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def stores_products_api(request):
    """
    List all products for a given store.
    """
    qs = Product.objects.select_related("store", "store__owner__vendor").order_by("name")

    p = request.query_params
    if p.get("store"):
        qs = qs.filter(store_id=p["store"])
    if p.get("vendor"):
        qs = qs.filter(store__owner__vendor__id=p["vendor"])
    if p.get("q"):
        qs = qs.filter(name__icontains=p["q"])
    if p.get("min_price"):
        qs = qs.filter(price__gte=p["min_price"])
    if p.get("max_price"):
        qs = qs.filter(price__lte=p["max_price"])
    if p.get("in_stock") in ("1", "true", "True"):
        qs = qs.filter(stock__gt=0)

    paginator = _paginator(request)
    page = paginator.paginate_queryset(qs, request)
    data = ProductPublicSerializer(page, many=True, context={"request": request}).data
    return paginator.get_paginated_response(data)