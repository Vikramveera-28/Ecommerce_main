# Complete Ecommerce Product Building Prompt

## Multi-Vendor Ecommerce Platform (Customer + Vendor + Logistics + Admin)

------------------------------------------------------------------------

# 1. Project Overview

Build a complete multi-vendor ecommerce platform similar to modern
marketplace systems.\
The system must support four workspaces:

-   Customer Workspace
-   Vendor Workspace
-   Logistics (Product Client) Workspace
-   Admin Workspace

The platform should support product listing, ordering, payment
processing, delivery tracking, returns, commission management, and
reporting.

------------------------------------------------------------------------

# 2. Core Functional Modules

## 2.1 Authentication & Role Management

Roles: - CUSTOMER - VENDOR - LOGISTICS - ADMIN

Features: - JWT Authentication - Role-based access control - Email
verification - Password reset - Account status (active, blocked,
pending)

------------------------------------------------------------------------

# 3. Database Structure (Relational Model)

## 3.1 Users Table

Table: users

-   id (PK)
-   name
-   email (unique)
-   phone
-   password_hash
-   role (customer/vendor/logistics/admin)
-   status (active/blocked/pending)
-   created_at
-   updated_at

------------------------------------------------------------------------

## 3.2 Customer Profile

Table: customer_profiles

-   id (PK)
-   user_id (FK -\> users.id)
-   date_of_birth
-   gender
-   default_address_id (FK -\> addresses.id)

------------------------------------------------------------------------

## 3.3 Vendor Profile

Table: vendor_profiles

-   id (PK)
-   user_id (FK -\> users.id)
-   store_name
-   store_description
-   gst_number
-   kyc_status
-   bank_account_number
-   ifsc_code
-   total_rating
-   created_at

------------------------------------------------------------------------

## 3.4 Logistics Profile

Table: logistics_profiles

-   id (PK)
-   user_id (FK -\> users.id)
-   vehicle_number
-   service_area
-   status

------------------------------------------------------------------------

## 3.5 Addresses

Table: addresses

-   id (PK)
-   user_id (FK -\> users.id)
-   full_name
-   phone
-   address_line_1
-   address_line_2
-   city
-   state
-   postal_code
-   country
-   is_default

------------------------------------------------------------------------

# 4. Product Management

## 4.1 Categories

Table: categories

-   id (PK)
-   name
-   parent_id (self FK)
-   image_url
-   status

------------------------------------------------------------------------

## 4.2 Products

Table: products

-   id (PK)
-   vendor_id (FK -\> vendor_profiles.id)
-   category_id (FK -\> categories.id)
-   name
-   description
-   price
-   discount_price
-   stock_quantity
-   sku
-   status (active/inactive)
-   created_at

------------------------------------------------------------------------

## 4.3 Product Images

Table: product_images

-   id (PK)
-   product_id (FK -\> products.id)
-   image_url
-   is_primary

------------------------------------------------------------------------

# 5. Cart & Wishlist

## 5.1 Cart

Table: cart

-   id (PK)
-   customer_id (FK -\> users.id)
-   product_id (FK -\> products.id)
-   quantity
-   created_at

------------------------------------------------------------------------

## 5.2 Wishlist

Table: wishlist

-   id (PK)
-   customer_id (FK -\> users.id)
-   product_id (FK -\> products.id)
-   created_at

------------------------------------------------------------------------

# 6. Order Management

## 6.1 Orders

Table: orders

-   id (PK)
-   customer_id (FK -\> users.id)
-   total_amount
-   payment_status (pending/paid/refunded)
-   order_status
    (pending/confirmed/shipped/delivered/cancelled/returned)
-   shipping_address_id (FK -\> addresses.id)
-   created_at

------------------------------------------------------------------------

## 6.2 Order Items

Table: order_items

-   id (PK)
-   order_id (FK -\> orders.id)
-   product_id (FK -\> products.id)
-   vendor_id (FK -\> vendor_profiles.id)
-   quantity
-   price

------------------------------------------------------------------------

# 7. Payments

## 7.1 Payments Table

Table: payments

-   id (PK)
-   order_id (FK -\> orders.id)
-   payment_method (upi/card/netbanking/cod)
-   transaction_id
-   amount
-   payment_status
-   created_at

------------------------------------------------------------------------

# 8. Logistics Management

## 8.1 Shipments

Table: shipments

-   id (PK)
-   order_id (FK -\> orders.id)
-   logistics_id (FK -\> logistics_profiles.id)
-   tracking_number
-   shipment_status
    (pickup/picked/shipped/out_for_delivery/delivered/failed)
-   updated_at

------------------------------------------------------------------------

# 9. Reviews

Table: reviews

-   id (PK)
-   product_id (FK -\> products.id)
-   customer_id (FK -\> users.id)
-   rating (1-5)
-   comment
-   created_at

------------------------------------------------------------------------

# 10. Commission System

Table: commissions

-   id (PK)
-   order_item_id (FK -\> order_items.id)
-   vendor_amount
-   platform_commission
-   commission_percentage

------------------------------------------------------------------------

# 11. Admin Features

-   Approve vendors
-   Manage categories
-   Monitor orders
-   Configure commission percentage
-   Generate sales reports
-   Manage coupons
-   Block users

------------------------------------------------------------------------

# 12. API Structure (REST Example)

Customer APIs: - GET /products - GET /products/{id} - POST /cart - POST
/orders - GET /orders

Vendor APIs: - POST /vendor/products - PUT /vendor/products/{id} - GET
/vendor/orders - PUT /vendor/orders/{id}/status

Logistics APIs: - GET /logistics/shipments - PUT
/logistics/shipments/{id}/status

Admin APIs: - GET /admin/users - PUT /admin/vendors/{id}/approve - GET
/admin/reports

------------------------------------------------------------------------

# 13. Recommended Tech Stack

Backend: Django / Flask\
Database: PostgreSQL\
Cache: Redis\
Queue: Celery\
Storage: AWS S3\
Payment Gateway: Razorpay / Stripe\
Authentication: JWT

------------------------------------------------------------------------

# 14. Advanced Features (Optional)

-   Real-time tracking
-   AI product recommendations
-   Wallet system
-   Referral system
-   Multi-language support
-   Notification service (Email/SMS)
-   Analytics dashboard

------------------------------------------------------------------------

# End of Ecommerce Product Building Prompt
