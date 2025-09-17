"""
URL configuration for ecommerce project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from shop import views
from shop.integrations import twitter_views 

urlpatterns = [
    path('admin/', admin.site.urls),

    # catalog & product
    path('', views.product_list, name='product_list'),
    path('post-login/', views.post_login, name='post_login'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),

    # basket & checkout
    path('basket/', views.basket_detail, name='basket_detail'),
    path('basket/add/<int:product_id>/', views.add_to_basket, name='add_to_basket'),
    path('basket/remove/<int:product_id>/', views.remove_from_basket, name='remove_from_basket'),
    path('checkout/', views.checkout, name='checkout'),

    # vendor
    path('vendor/', views.vendor_store_list, name='vendor_store_list'),
    path('vendor/stores/add/', views.store_add, name='store_add'),
    path('vendor/stores/<int:pk>/', views.store_products, name='store_products'),
    path('vendor/stores/<int:pk>/edit/', views.store_edit, name='store_edit'),
    path('vendor/stores/<int:pk>/delete/', views.store_delete, name='store_delete'),
    path('vendor/stores/<int:store_pk>/products/add/', views.product_add, name='product_add'),
    path('vendor/stores/<int:store_pk>/products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('vendor/stores/<int:store_pk>/products/<int:pk>/delete/', views.product_delete, name='product_delete'),

    # registration
    path("register/customer/", views.register_customer, name="register_customer"),
    path('register/vendor/', views.register_vendor, name='register_vendor'),

    # auth (login/logout, optional built-in reset pages)
    path('accounts/', include('django.contrib.auth.urls')),

    # custom account utils
    path('forgot-username/', views.forgot_username, name='forgot_username'),
    path('account/reset/', views.send_password_reset, name="send_password_reset"),
    path('account/reset/<str:token>/', views.reset_user_password, name="reset_user_password"),


    # APIs
    path('get/stores/', views.view_stores, name='view_stores'),
    path('post/stores/', views.add_store, name='add_store'),
    path('stores/<int:store_id>/products/add/', views.add_product, name="add_product"),
    path('stores/<int:store_id>/products/', views.list_products, name="list_products"),
    path('vendors/stores/', views.vendor_stores, name="vendor_stores"),    
    path('stores/products/', views.stores_products_api, name="stores_products_api"),
    path('my/reviews/', views.my_product_reviews, name="my_product_reviews"),

    # Twitter
    path("twitter/start/", twitter_views.start_auth, name="twitter_start_auth"),
    path("twitter/callback", twitter_views.callback, name="twitter_callback"),
    
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
