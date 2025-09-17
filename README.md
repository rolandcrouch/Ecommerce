# Django eCommerce Platform

A full-featured eCommerce web application built with **Django 5** and **Django REST Framework**, supporting vendor store management, product listings, shopping baskets, checkout, customer accounts, and product reviews.  
The project also integrates with the **Twitter/X API** to post updates when new stores or products are created.

---

## Features

- **Product Catalog**
  - Browse products with details, images, stock levels, and pricing.
  - Product reviews and ratings (1–5 stars).

- **Basket & Checkout**
  - Add/remove items from basket.
  - Checkout flow with order creation and payment status tracking.

- **Vendor Management**
  - Vendor registration and profile creation.
  - Create and manage multiple stores.
  - Add, edit, and delete products.

- **Customer Accounts**
  - Customer registration, login/logout, and password reset.
  - Track purchased products.

- **REST API**
  - Endpoints for managing stores, products, and reviews.

- **Integrations**
  - Optional Twitter/X integration for automated tweets about new stores and products.
  - Email integration for password resets (SMTP via Gmail configured).

---

## Quickstart

```bash
# 1. Clone the repository
git clone https://github.com/.......git
cd <the-repo>

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up the database (MariaDB or SQLite)
# For MariaDB, ensure you have a database created and update settings in ecommerce/settings.py
# For SQLite, uncomment the provided config in settings.py

# 5. Run migrations
python manage.py migrate

# 6. Create a superuser for the Django admin
python manage.py createsuperuser

# 7. Start the development server
python manage.py runserver
```

Visit the app at:  
👉 http://127.0.0.1:8000/

---

## Twitter/X API Integration

This project integrates with the Twitter (X) API for posting automated updates.  

In order to collect a TW_CLIENT_ID & TW_CLIENT_SECRET you will need a dev ops account with 
Twitter (X).

1. Make sure your `.env` file includes valid credentials:
   ```ini
   TWITTER_AUTH_MODE=oauth2
   TW_CLIENT_ID=your-client-id
   TW_CLIENT_SECRET=your-client-secret
   TW_REDIRECT_URI=http://127.0.0.1:8000/twitter/callback
   ```

2. Start the server:
   ```bash
   python manage.py runserver
   ```

3. In your browser, go to:
   👉 http://127.0.0.1:8000/twitter/start/

   You will be redirected to Twitter/X to authorize the app.

4. After authorizing, you will be redirected back to the ecommerce app!:
   👉 http://127.0.0.1:8000 

   Your access tokens will be stored locally in `.twitter_tokens.json`.

---

## Configuration

This project uses **environment variables** managed via `django-environ`.  
Create a `.env` file in the project root with values like:

```ini
# Django
DJANGO_SECRET_KEY=your-secret-key
DEBUG=True

# Database
DB_NAME=ecommerce
DB_USER=ecom_user
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=3306

# Email
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Twitter API
TWITTER_AUTH_MODE=oauth2
TW_CLIENT_ID=your-client-id
TW_CLIENT_SECRET=your-client-secret
TW_REDIRECT_URI=http://127.0.0.1:8000/twitter/callback
```

---

### API Endpoints (selection)

- `GET /get/stores/` → List all stores  
- `POST /post/stores/` → Add a new store  
- `POST /stores/<id>/products/add/` → Add a product to a store  
- `GET /stores/<id>/products/` → List products in a store  
- `GET /my/reviews/` → Get reviews for logged-in user  

---

## Project Structure

```
ecommerce/
├── manage.py
├── ecommerce/
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── media/
│     └── products/
└── shop/
│    ├── __init__.py
│    ├── models.py
│    ├── views.py
│    ├── forms.py
│    ├── basket.py
│    ├── helpers.py
│    ├── signals.py
│    ├── admin.py
│    ├── apps.py
│    ├── utils.py
│    └──functions/
│        ├── tweet.py
│    └──integrations/
│        ├── twitter_views.py
│    └── templates/
│        └── shop/
│            ├── add_prouct.html
│            ├── product_detail.html
│            ├── product_list.html
│            ├── basket_detail.html
│            ├── register.html
│            ├── vendor_fields.html
│            ├── vendor_store_list.html
│            ├── store_product_list.html
│            ├── product_form.html
│            ├── store_form.html
│            ├── store_edit.html
│            └── Emails
│                ├── invoice.html
│        └── registration/
│            ├── login.html
│            ├── reset_password_confirm_page.html
│            ├── request_password_reset.html
│            ├── forgot_username.html
```

---

## Roadmap / Known Issues

- Add support for online payments (Stripe/PayPal integration).
- Improve vendor analytics dashboard.
- Enhance REST API with authentication and permissions.

---

## Contributing

1. Fork the repository  
2. Create a new branch (`git checkout -b feature/new-feature`)  
3. Commit changes (`git commit -m 'Add new feature'`)  
4. Push to branch (`git push origin feature/new-feature`)  
5. Open a Pull Request  

---

## Maintainers

- Roland Crouch – rolandcrouch@gmail.com
