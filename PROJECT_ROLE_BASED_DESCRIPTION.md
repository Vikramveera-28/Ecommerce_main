# Multi-Vendor Ecommerce Platform: Detailed Role-Based Project Description

## 1) Project Summary

This project is a role-based multi-vendor ecommerce platform with:

- `Flask + SQLAlchemy` backend API
- `React + Vite` single frontend app
- JWT authentication with role-based access control
- Dedicated workspaces for:
  - `Customer`
  - `Vendor` (you wrote "vender"; in code it is `vendor`)
  - `Logistics`
  - `Admin`
- Seed-import pipeline from `ecommerce.db` into the platform schema

Core objective:

- Let customers browse, save, cart, checkout, and track orders.
- Let vendors manage product listings and vendor-side order handling.
- Let logistics users manage shipment movement and proof/OTP delivery.
- Let admins moderate users/vendors/products and monitor platform sales.


## 2) Architecture and Technical Design

### Backend

- Framework: Flask
- ORM: SQLAlchemy
- Auth: `flask-jwt-extended` (access + refresh tokens)
- Rate limiting: `flask-limiter`
- DB: SQLite default (`sqlite:///ecommerce_app.db`)
- Main API prefix: `/api/v1`

### Frontend

- Framework: React
- Router: `react-router-dom`
- API client: centralized fetch wrapper (`frontend/src/api/client.js`)
- Auth persistence: localStorage (`market_auth_state`)
- Role guards: route-level access checks + redirection to role home

### Security Controls Implemented

- JWT required for protected endpoints
- Role checks and active-account checks on protected routes
- Revoked token store for logout invalidation
- Rate limits:
  - Register: `10/min`
  - Login: `20/min`
  - Create order: `20/hour`


## 3) Data Model and Business Objects

Key entities implemented:

- Users and role profiles (`customer_profiles`, `vendor_profiles`, `logistics_profiles`)
- Product catalog (`categories`, `products`, `product_images`, `tags`, `reviews`)
- Shopping entities (`cart_items`, `wishlist_items`, `addresses`)
- Transaction entities (`orders`, `order_items`, `payments`, `shipments`, `commissions`)
- Moderation/audit entities (`revoked_tokens`, soft-delete timestamps, audit fields)

Important enums used in behavior:

- Role: `customer`, `vendor`, `logistics`, `admin`
- Account status: `pending`, `active`, `blocked`
- Vendor KYC: `pending`, `approved`, `rejected`
- Product approval: `pending`, `approved`, `rejected`
- Order status: `pending`, `confirmed`, `packed`, `shipped`, `delivered`, `cancelled`, `returned`
- Payment status: `cod_pending`, `cod_confirmed`, `paid`, `refunded`
- Shipment status: `pickup_requested`, `picked`, `in_transit`, `out_for_delivery`, `delivered`, `failed`


## 4) Authentication, Authorization, and Account Lifecycle

### Registration Rules

- `Customer` self-registers and becomes `active` immediately.
- `Vendor` self-registers as `pending`; cannot log in until activated.
- `Logistics` self-registers as `pending`; cannot log in until activated.
- `Admin` self-registration is blocked.

### Login Rules

- Only `active` users can log in.
- `pending` or `blocked` users get access denied.

### Role Enforcement

Protected route decorator checks:

1. JWT validity
2. User exists
3. User status is `active`
4. User role is allowed for endpoint


## 5) End-to-End Marketplace Lifecycle

### Product Lifecycle

1. Vendor creates product -> product starts as `approval_status=pending`.
2. Admin approves product -> `approval_status=approved`, `status=active`.
3. If rejected -> `approval_status=rejected`, `status=inactive`.

### Order Lifecycle

1. Customer places order from cart or direct item list.
2. System creates order + order items + commission rows.
3. Shipment auto-created with tracking number and OTP.
4. Vendor and/or logistics updates status through their workflows.
5. Customer can cancel only in `pending` or `confirmed`.

### Payment Lifecycle

- COD order starts as `cod_pending`
- Vendor marking delivered sets COD to `cod_confirmed`
- Card flow sets payment `paid` immediately (internal simulated card flow)

### Shipment Lifecycle

- Starts as `pickup_requested`
- Logistics moves through delivery stages
- Delivery requires OTP
- Delivered shipment updates order to delivered


## 6) Role-by-Role Detailed Functional Description

---

## Customer Role

### A) Main Purpose

- Discover products
- Save favorites
- Build cart
- Manage addresses/payment profile card
- Place orders (COD or saved-card flow)
- Track and cancel eligible orders

### B) Customer Workspace Pages and Activities

1. `/customer/home`
- Shows top-rated/trending products (rating sort)
- Quick add-to-cart from product tiles

2. `/customer/products`
- Full catalog browsing
- Search by keyword (`q`)
- Category filtering
- Sorting (`newest`, `top rated`, `price asc`, `price desc`)
- Pagination

3. `/customer/products/:id`
- Product detail with image gallery
- Related products
- Add to cart / add to wishlist
- Tabs: overview, specs, reviews

4. `/customer/favorites`
- View wishlist
- Remove favorite
- Move favorite item to cart

5. `/customer/cart`
- View cart lines
- Increment/decrement quantity
- Remove item
- Clear entire cart
- View subtotal, tax, total estimate

6. `/customer/payment` (checkout)
- Select saved address or add new address
- Choose shipping method (standard/express)
- Choose payment method (`cod` or `card`)
- Place order

7. `/customer/orders`
- View all orders with status filtering/search
- Open order details/invoice/processing/delivery modals
- Cancel allowed orders (`pending`, `confirmed` only)
- View shipment tracking number and delivery OTP

8. `/customer/profile`
- View account/order stats
- Add addresses
- Save/update payment card profile
- View existing saved addresses/card summary

### C) Customer API Capabilities

- Auth:
  - `POST /auth/register`
  - `POST /auth/login`
  - `POST /auth/refresh`
  - `POST /auth/logout`
- Catalog:
  - `GET /products`, `/products/{id}`, `/categories`, `/vendors`
- Cart/Wishlist:
  - `GET/POST/PATCH/DELETE /cart/items`
  - `GET/POST/DELETE /wishlist/items`
- Address and card profile:
  - `GET/POST /addresses`
  - `GET/PUT /payment-card`
- Orders:
  - `POST /orders`
  - `GET /orders`
  - `GET /orders/{id}`
  - `POST /orders/{id}/cancel`

### D) Customer Workflow (Typical)

1. Register as customer -> auto-active.
2. Login.
3. Browse products and add items to cart/wishlist.
4. Add shipping address.
5. (Optional) Save card in Profile.
6. Checkout and place order.
7. Track shipment and status from Orders.
8. Cancel only if still in allowed order stage.

### E) Customer Validations and Constraints

- Cart quantity cannot exceed product stock.
- Address creation requires core fields.
- Card save requires:
  - cardholder name
  - 12-19 digit card number
  - exactly 4-digit PIN
- Card checkout requires matching saved card number + PIN.
- Order placement needs valid owned shipping address.

### F) Customer Limitations in Current Build

- No address update/delete endpoint yet (only create/list).
- Promo code behavior is UI placeholder.
- No review submission endpoint in current customer UI/API.


---

## Vendor Role

### A) Main Purpose

- Manage product portfolio and inventory
- Submit products for admin approval
- View vendor order lines
- Update order statuses
- Monitor dashboard metrics

### B) Vendor Account Lifecycle

1. Register as vendor -> user status `pending`, KYC profile `pending`.
2. Cannot log in until admin approval activates account.
3. Admin approval sets:
  - vendor KYC = `approved`
  - user status = `active`

### C) Vendor Workspace Pages and Activities

1. `/vendor/dashboard`
- KPI cards (revenue/orders/AOV/pending approval)
- Sales trend chart (current vs previous period)
- Top performing products table

2. `/vendor/products`
- Monitoring view:
  - search/filter by category/stock
  - inventory value, low stock, out-of-stock metrics
  - CSV export
  - selectable rows for future bulk actions
- Add Product view:
  - create product with name, SKU, category, price, stock, description
  - submits as pending approval

3. `/vendor/orders`
- Vendor order-line list
- Update order status using dropdown:
  - `confirmed`, `packed`, `shipped`, `delivered`, `cancelled`

### D) Vendor API Capabilities

- `GET /vendor/products`
- `POST /vendor/products`
- `PATCH /vendor/products/{id}`
- `GET /vendor/orders`
- `PATCH /vendor/orders/{id}/status`

### E) Vendor Workflow (Typical)

1. Get approved by admin.
2. Login to vendor workspace.
3. Create products (pending moderation).
4. Track approvals and inventory.
5. Process incoming order lines.
6. Update order status as fulfillment progresses.

### F) Vendor Business Rules and Constraints

- Product creation blocked if vendor KYC not approved.
- SKU must be unique platform-wide.
- Category must exist.
- Price must be > 0.
- Stock quantity cannot be negative.
- On vendor status update to `delivered`:
  - order payment status updated to COD confirmed
  - payment record updated accordingly

### G) Vendor Limitations in Current Build

- UI "Import Stock" and some update controls are placeholders.
- No rich media upload API currently wired in vendor create form.
- Status transition guards are permissive (can jump between valid states).


---

## Logistics Role

### A) Main Purpose

- Manage shipment queue
- Claim unassigned shipments
- Update shipment progress
- Confirm delivery with OTP

### B) Logistics Account Lifecycle

1. Register as logistics -> user status `pending`.
2. Needs activation by admin (or seed logistics user).
3. Active logistics users can access shipment workspace.

### C) Logistics Workspace Pages and Activities

1. `/logistics/shipments`
- List shipments assigned to logistics user plus unassigned ones
- Update shipment status:
  - `picked`
  - `in_transit`
  - `out_for_delivery`
  - `delivered` (requires OTP)
  - `failed`

### D) Logistics API Capabilities

- `GET /logistics/shipments`
- `PATCH /logistics/shipments/{id}/status`

### E) Logistics Workflow (Typical)

1. Login to shipment board.
2. Open assigned/unassigned shipments.
3. Take shipment and move through delivery stages.
4. Enter OTP to mark delivered.
5. Order status auto-syncs to shipped/delivered as shipment moves.

### F) Logistics Rules and Constraints

- Cannot modify shipment assigned to another logistics user.
- Unassigned shipment auto-assigns to current logistics profile on first update.
- Delivery status requires matching OTP if OTP exists.
- Shipment updates also update linked order status:
  - picked/in_transit/out_for_delivery -> order becomes `shipped`
  - delivered -> order becomes `delivered`

### G) Logistics Limitations in Current Build

- Basic shipment list UI (no map/route optimization).
- Proof-of-delivery URL is supported in API but not fully exposed in current logistics UI.


---

## Admin Role

### A) Main Purpose

- Moderate platform actors and listings
- Activate/block user access
- Approve vendors and products
- Monitor sales performance and COD behavior

### B) Admin Access Characteristics

- Cannot self-register from public register endpoint.
- Typically created via seed import/default seed account.

### C) Admin Workspace Pages and Activities

1. `/admin/dashboard`
- Sales report summary:
  - total orders
  - total revenue
  - COD confirmed order count
- Order status distribution view

2. `/admin/users`
- List users
- Activate or block accounts

3. `/admin/moderation`
- Vendor moderation:
  - approve vendor KYC
  - activate vendor account
- Product moderation:
  - approve products pending review

4. Logistics oversight
- Admin also has permission to use logistics shipment APIs and frontend shipment route.

### D) Admin API Capabilities

- `GET /admin/users`
- `PATCH /admin/users/{id}/status`
- `PATCH /admin/vendors/{id}/approve`
- `PATCH /admin/products/{id}/approve`
- `GET /admin/reports/sales`
- Plus shipment APIs through dual-role allowance (`admin` + `logistics`)

### E) Admin Workflow (Typical)

1. Review pending vendors/products in moderation.
2. Approve vendor KYC so vendor can operate.
3. Approve/reject product listings.
4. Monitor sales and COD metrics in dashboard.
5. Activate/block users from user management.

### F) Admin Rules and Constraints

- Vendor approval endpoint also updates linked user role/status.
- Product approval endpoint can approve or reject using payload flag.
- User status endpoint accepts valid account status only.

### G) Admin Limitations in Current Build

- UI focuses on approve actions; reject actions are API-capable but not richly surfaced.
- Reporting is operational summary, not deep BI export.


## 7) Role vs Capability Matrix

| Capability | Customer | Vendor | Logistics | Admin |
|---|---|---|---|---|
| Browse catalog | Yes | Yes (indirect) | No | Yes |
| Cart/Wishlist | Yes | No | No | No |
| Place orders | Yes | No | No | No |
| Cancel own orders | Yes (stage-limited) | No | No | No |
| Create products | No | Yes (KYC approved only) | No | No |
| Approve products | No | No | No | Yes |
| Update vendor order status | No | Yes | No | No |
| View shipments | No | No | Yes (assigned/unassigned) | Yes |
| Update shipment status | No | No | Yes | Yes |
| User moderation | No | No | No | Yes |
| Sales report access | No | No | No | Yes |


## 8) Seed Data and Default Operational Accounts

From seed workflow:

- Source catalog import from `ecommerce.db`
- Default admin:
  - email: `admin@seed.local`
  - password: `admin12345`
- Default logistics:
  - email: `logistics@seed.local`
  - password: `logistics12345`

Also generated during import:

- Vendor users (default password pattern known in code: `vendor12345`)
- Seed customer users for historical reviews (default `customer12345`)


## 9) Important Implementation Notes

1. Catalog listing endpoint currently returns all non-deleted products; moderation visibility can be filtered by `approval_status` query but not strictly hidden by default.
2. Card payment is an internal profile-card verification flow, not external payment gateway integration.
3. Shipment OTP is generated at order creation and used for delivery confirmation.
4. Commission records are created per order item (default 10% platform commission).
5. Frontend has some placeholder actions (promo, import stock, edit/remove address UI hints) that are not fully API-wired yet.


## 10) Practical End-to-End Usage Story (All Roles)

1. Customer browses products, adds to cart, places order with COD/card.
2. System creates order, payment row, shipment row, and commissions.
3. Vendor sees order line and updates fulfillment status.
4. Logistics picks shipment, updates transit states, and delivers using OTP.
5. Customer tracks progress and sees delivered completion.
6. Admin monitors sales and COD confirmation, and moderates any pending vendors/products.

