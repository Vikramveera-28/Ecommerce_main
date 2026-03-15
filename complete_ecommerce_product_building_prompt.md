# 🛒 Complete Ecommerce Product Building Prompt

## 🎯 Objective

Build a **production-level, multi-vendor ecommerce platform** with four
workspaces: - Customer Workspace - Vendor Workspace - Product Client
(Logistics) Workspace - Admin Workspace

The system must be scalable, secure, modular, and API-driven.

------------------------------------------------------------------------

# 🏗 System Architecture Requirements

-   Backend: Django / Flask (REST API based)
-   Database: PostgreSQL
-   Authentication: JWT with role-based access
-   Cache: Redis (cart + sessions)
-   Background Tasks: Celery
-   Storage: AWS S3 (product images)
-   Payment Gateway Integration
-   Email & SMS notification system
-   Dockerized deployment
-   Production-ready structure

------------------------------------------------------------------------

# 👤 1️⃣ CUSTOMER WORKSPACE

## Pages Required

-   Home Page (banners, featured products, trending categories)
-   Category Page (filter, sort, pagination)
-   Product Listing Page
-   Product Detail Page (images, reviews, stock, vendor info)
-   Cart Page
-   Checkout Page
-   Order List Page
-   Wishlist Page
-   Profile Page

## Functional Requirements

-   User registration & login
-   Add to cart
-   Save wishlist
-   Apply coupons
-   Secure payment
-   Track order status
-   Return & replace request
-   Download invoice

------------------------------------------------------------------------

# 🏪 2️⃣ VENDOR WORKSPACE

## Pages Required

-   Dashboard (sales summary, analytics)
-   Product Management (Add/Edit/Delete)
-   Stock Management
-   Order Management (Accept/Reject)
-   Returns Management
-   Earnings & Payout Page
-   Reviews Management
-   Vendor Profile & KYC

## Functional Requirements

-   Upload products with multiple images
-   Bulk upload via CSV
-   Manage inventory
-   Accept or reject orders
-   Initiate refund
-   Track earnings
-   Request pickup

------------------------------------------------------------------------

# 🚚 3️⃣ PRODUCT CLIENT (LOGISTICS) WORKSPACE

## Pages Required

-   Dashboard (assigned pickups & deliveries)
-   Pickup Management
-   Delivery Management
-   Return Pickup Management
-   Warehouse Management (Optional)

## Functional Requirements

-   Accept pickup requests
-   Update delivery status
-   OTP-based delivery confirmation
-   Upload proof of delivery
-   Manage return logistics

------------------------------------------------------------------------

# 👑 4️⃣ ADMIN WORKSPACE

## Pages Required

-   Admin Dashboard
-   User Management
-   Vendor Approval
-   Product Approval
-   Order Monitoring
-   Payment & Commission Setup
-   Coupon Management
-   Banner & CMS Management
-   Reports & Analytics
-   Support Ticket Management

## Functional Requirements

-   Approve vendors
-   Approve products
-   Set commission percentage
-   Manage refunds
-   Block users
-   Manage homepage banners
-   View platform-wide analytics

------------------------------------------------------------------------

# 🗄 Database Design Requirements

## Core Tables

-   Users (Role-based: customer, vendor, logistics, admin)
-   Products
-   Categories
-   Product Images
-   Cart
-   Orders
-   Order Items
-   Payments
-   Reviews
-   Wishlist
-   Returns
-   Coupons
-   Vendor Payouts

Include: - Proper foreign keys - Indexing - Soft delete support -
Timestamps (created_at, updated_at)

------------------------------------------------------------------------

# 🔐 Security Requirements

-   JWT Authentication
-   Role-based permission control
-   CSRF protection
-   Rate limiting
-   Secure password hashing
-   HTTPS enforcement

------------------------------------------------------------------------

# 📦 API Requirements

Create REST APIs for:

### Authentication

-   Register
-   Login
-   Logout
-   Refresh token

### Product APIs

-   List products
-   Filter products
-   Product detail
-   Create product (vendor)
-   Update product
-   Delete product

### Order APIs

-   Create order
-   Update order status
-   Track order
-   Cancel order

### Admin APIs

-   Approve vendor
-   Approve product
-   Manage commission
-   Generate reports

------------------------------------------------------------------------

# 📊 Advanced Features (Recommended)

-   AI-based product recommendations
-   Real-time order tracking
-   Multi-language support
-   Multi-currency support
-   Referral system
-   Wallet system
-   Subscription (Prime model)
-   Flash sales system
-   Inventory alert system

------------------------------------------------------------------------

# 🚀 Expected Output

The final system should: - Support multi-vendor ecommerce - Handle high
traffic - Be fully API-based - Be scalable - Be production-ready - Be
secure - Be modular for future expansion

------------------------------------------------------------------------

# 📝 Instruction to Developer / AI

Build the complete ecommerce system following the above requirements.
Ensure clean architecture, reusable components, and scalable database
design. Provide full backend structure, models, APIs, and role-based
access control.
