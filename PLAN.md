# Multi-Vendor Ecommerce Build Plan (Using Attached `ecommerce.db` Data)

## Summary
Build a production-grade, API-first multi-vendor ecommerce platform with:
1. `Flask + SQLAlchemy` backend.
2. Single `React` app with role-based workspaces (customer, vendor, logistics, admin).
3. Phased delivery: MVP first, then full platform features.
4. One-time bootstrap import from `ecommerce.db` into PostgreSQL.
5. COD-only payment in MVP (gateway integration deferred).
6. Deployment planning explicitly paused for now.

## Confirmed Decisions
1. Backend stack: `Flask + SQLAlchemy`.
2. Delivery strategy: `MVP -> full platform`.
3. Vendor seeding: auto-create vendors from product brand.
4. Frontend: React UI included.
5. React architecture: single app with role routes.
6. Payments: cash on delivery only for now.
7. Data mode: one-time bootstrap import from SQLite.
8. Deployment: deferred from current plan.

## Current Data Reality (from attached DB)
1. Tables: `products (150)`, `product_images (315)`, `product_tags (271)`, `product_reviews (450)`.
2. Catalog only: no users, vendors, carts, orders, payments, logistics, admin data.
3. Brands: 48 non-null brands, 76 products with null brand.
4. Categories: 15.
5. Reviews: 450 rows, 179 unique reviewer emails.
6. Product `rating` and review-average ratings are mostly inconsistent, so rating must be normalized during import.

## Implementation Blueprint

## 1) Repo and Service Structure
1. Backend modules:
   - `auth` (JWT, roles, account status)
   - `catalog` (products, categories, media, tags, search/filter)
   - `cart_wishlist`
   - `orders` (order lifecycle, COD handling)
   - `payments` (COD-only service adapter)
   - `vendor_portal`
   - `logistics`
   - `admin`
   - `seed_import` (SQLite -> PostgreSQL bootstrap)
2. Frontend modules in one React app:
   - `workspace/customer/*`
   - `workspace/vendor/*`
   - `workspace/logistics/*`
   - `workspace/admin/*`
   - shared auth/route guards/layout/theme/api client.

## 2) Data Model and Migration Plan
1. Core tables (PostgreSQL): users, profiles, addresses, categories, vendors, products, product_images, tags, product_tags_map, reviews, cart, wishlist, orders, order_items, payments, shipments, returns, commissions, coupons, payouts.
2. Add soft-delete fields: `deleted_at` on business entities.
3. Add audit fields on all mutable entities: `created_at`, `updated_at`, `created_by`, `updated_by` where applicable.
4. Add critical constraints/indexes:
   - unique: `users.email`, `products.sku`, `categories.slug`, `vendors.store_slug`.
   - indexes: `(products.category_id, status)`, `(products.vendor_id)`, `(orders.customer_id, created_at)`, `(order_items.order_id)`, `(reviews.product_id, created_at)`.
5. Order/payment status enums (locked):
   - order: `pending -> confirmed -> packed -> shipped -> delivered | cancelled | returned`.
   - payment: `cod_pending`, `cod_confirmed`, `refunded`.
   - shipment: `pickup_requested`, `picked`, `in_transit`, `out_for_delivery`, `delivered`, `failed`.

## 3) Bootstrap Import Plan (`ecommerce.db`)
1. Import staging:
   - Copy SQLite rows into staging tables first.
   - Validate schema and row counts before transform.
2. Vendor mapping rule:
   - One vendor per non-null brand.
   - Null brand products map to single vendor: `Unbranded Marketplace`.
3. Category mapping:
   - Convert category strings to normalized `slug` + title.
4. Product mapping:
   - Preserve source product id as `legacy_product_id`.
   - Preserve SKU as unique key.
   - Map discount% into computed `discount_price`.
5. Image mapping:
   - Merge `thumbnail` and `product_images`.
   - Mark first image as primary; deduplicate by URL.
6. Tag mapping:
   - Normalize tags to lowercase trimmed strings.
   - Upsert tag dictionary + join table.
7. Review mapping:
   - Create seed customer users from unique reviewer emails (`seed+<hash>@local` fallback if invalid).
   - Insert reviews linked to created customer ids.
8. Rating normalization:
   - Canonical product rating = `AVG(review.rating)` when reviews exist.
   - Fallback to source product rating only when no reviews.
9. Idempotency:
   - Import command uses upsert strategy keyed by `legacy_product_id`, SKU, vendor slug, category slug.
10. Validation gates:
   - Hard fail if product count mismatch.
   - Hard fail on duplicate SKU after normalization.
   - Warn (not fail) on malformed URL fields.

## 4) Public APIs / Interfaces (Important)
1. Auth:
   - `POST /api/v1/auth/register`
   - `POST /api/v1/auth/login`
   - `POST /api/v1/auth/refresh`
   - `POST /api/v1/auth/logout`
2. Catalog:
   - `GET /api/v1/products`
   - `GET /api/v1/products/{id}`
   - `GET /api/v1/categories`
   - `GET /api/v1/search`
3. Customer:
   - `POST /api/v1/cart/items`
   - `PATCH /api/v1/cart/items/{id}`
   - `DELETE /api/v1/cart/items/{id}`
   - `POST /api/v1/orders`
   - `GET /api/v1/orders`
   - `GET /api/v1/orders/{id}`
   - `POST /api/v1/orders/{id}/cancel`
   - `POST /api/v1/wishlist/items`
4. Vendor:
   - `POST /api/v1/vendor/products`
   - `PATCH /api/v1/vendor/products/{id}`
   - `GET /api/v1/vendor/orders`
   - `PATCH /api/v1/vendor/orders/{id}/status`
5. Logistics:
   - `GET /api/v1/logistics/shipments`
   - `PATCH /api/v1/logistics/shipments/{id}/status`
6. Admin:
   - `GET /api/v1/admin/users`
   - `PATCH /api/v1/admin/vendors/{id}/approve`
   - `PATCH /api/v1/admin/products/{id}/approve`
   - `GET /api/v1/admin/reports/sales`
7. Interface/type additions:
   - `Role = CUSTOMER | VENDOR | LOGISTICS | ADMIN`
   - `AccountStatus = ACTIVE | BLOCKED | PENDING`
   - `PaymentMethod = COD`
   - `OrderStatus`, `ShipmentStatus`, `VendorKycStatus` enums as backend/frontend shared contract.

## 5) React App Plan (Single App, Role Routes)
1. Routing shell:
   - `/customer/*`, `/vendor/*`, `/logistics/*`, `/admin/*`.
2. Auth:
   - JWT session handling, refresh token flow, role guard + status guard.
3. MVP pages:
   - Customer: home, category/search, product detail, cart, checkout(COD), orders.
   - Vendor: dashboard lite, product CRUD, order list/status updates.
   - Logistics: shipment queue, status update page.
   - Admin: vendor approval, product approval, user block/unblock, basic reports.
4. Phase-2 pages:
   - coupons, returns, commission setup UI, CMS banners, advanced analytics, support tickets.

## 6) Security and Operational Controls
1. JWT with short-lived access + refresh rotation.
2. Password hashing with strong scheme (`argon2` or `bcrypt`).
3. Role and ownership checks at service layer and endpoint decorator layer.
4. Rate limiting on auth and checkout endpoints.
5. Input validation + strict schema contracts for all POST/PATCH endpoints.
6. Audit logging for admin actions and order/payment status transitions.

## 7) Phased Delivery Plan

### Phase A (Foundation, Week 1-2)
1. Scaffold backend/frontend projects and shared API contract package.
2. Configure PostgreSQL, Redis, Celery, Alembic migrations.
3. Implement auth + roles + user/profile models.
4. Build import pipeline skeleton and dry-run validation.

### Phase B (Catalog + Seed Import, Week 3)
1. Implement catalog/category/vendor/product/media/tag/review models and APIs.
2. Complete SQLite bootstrap import command.
3. Run import and reconcile counts against source.
4. Implement customer browsing/search/filter UI.

### Phase C (Cart/Order/COD MVP, Week 4-5)
1. Cart and wishlist APIs + UI.
2. Checkout API with COD-only payment flow.
3. Order creation, status machine, order history UI.
4. Basic vendor order management and logistics shipment assignment/status.

### Phase D (Admin Core + Hardening, Week 6)
1. Admin approvals (vendor/product), user moderation, base reports.
2. Commission calculation per order item.
3. Security hardening, audit logs, API error model unification.

### Phase E (Full Platform Extensions, Week 7-8)
1. Returns/refunds workflow.
2. Coupons and payouts modules.
3. Optional advanced features from prompt (tracking improvements, recommendations hooks).
4. Performance tuning and final QA pass.

## 8) Testing Plan and Acceptance Scenarios

### Automated Tests
1. Unit tests for services: auth, product import mapping, order status transitions, commission logic.
2. API integration tests for each role with positive/negative authorization cases.
3. Import tests:
   - expected products=150, images=315, tags=271, reviews=450 imported.
   - no orphaned product relations.
   - unique SKU preserved.
4. Frontend tests:
   - route guards by role/status.
   - cart/checkout/order flow.
   - vendor/admin critical workflows.

### End-to-End Scenarios
1. Customer places COD order, vendor accepts, logistics delivers, order closes.
2. Customer cancel before shipping.
3. Admin blocks user and access is revoked immediately.
4. Vendor with pending approval cannot publish products.
5. Seed import idempotency: running import twice produces no duplicates.

### MVP Acceptance Criteria
1. All MVP endpoints functional with auth + RBAC.
2. React app supports working flows for all 4 roles at MVP scope.
3. Source dataset fully available in platform catalog after import.
4. COD checkout works end-to-end with auditable order/payment state.

## 9) Explicit Assumptions and Defaults
1. SQLite file is trusted as one-time seed source and not used at runtime.
2. Products with null brand are assigned to `Unbranded Marketplace` vendor.
3. Product rating shown to users uses normalized review-average rating.
4. Guest review users are seeded from reviewer email/name to preserve historical reviews.
5. Payment gateway integration is intentionally deferred; COD is the only enabled payment method.
6. Deployment architecture and rollout environments are intentionally paused and excluded from implementation scope right now.
