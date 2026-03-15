# Multi-Vendor Ecommerce Platform

Production-oriented scaffold implementing:
- Flask + SQLAlchemy backend with JWT RBAC
- Single React app with role-based workspaces
- COD checkout flow
- One-time SQLite seed import (`ecommerce.db`)

## Repository Structure

- `backend/` Flask API, models, seed import command, tests
- `frontend/` React + Vite role-routed web app
- `ecommerce.db` source catalog data

## Backend Quick Start

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

Set env (optional, defaults work for local SQLite):

```bash
copy .env.example .env
```

Initialize DB and import seed data:

```bash
flask --app manage.py init-db
flask --app manage.py seed-import --sqlite-path ..\\ecommerce.db
python manage.py
```

Health check:

- `GET http://localhost:5000/health`

Default seed admin (can be overridden via env):
- Email: `admin@seed.local`
- Password: `admin12345`

Default seed logistics (can be overridden via env):
- Email: `logistics@seed.local`
- Password: `logistics12345`

## Frontend Quick Start

```bash
cd frontend
copy .env.example .env
cmd /c npm install
cmd /c npm run dev
```

Open: `http://localhost:5173`

## Core API Surface

- Auth: `/api/v1/auth/register`, `/login`, `/refresh`, `/logout`
- Catalog: `/api/v1/products`, `/products/{id}`, `/categories`, `/search`, `/vendors`
- Customer: `/api/v1/cart/*`, `/wishlist/*`, `/addresses`, `/orders*`
- Vendor: `/api/v1/vendor/products*`, `/orders*`
- Logistics: `/api/v1/logistics/shipments*`
- Admin: `/api/v1/admin/users*`, `/vendors/{id}/approve`, `/products/{id}/approve`, `/reports/sales`

## Tests

```bash
cd backend
pytest
```

## Notes

- COD is the only payment method enabled in this build.
- Deployment setup is intentionally deferred.
- `seed-import` uses staging tables and idempotent upsert logic.
