# Multi-Vendor Ecommerce Platform

Production-oriented scaffold implementing:
- Flask backend with JWT RBAC and MongoDB auth mode
- Root React + Vite app with role-based workspaces
- COD checkout flow
- One-time SQLite seed import (`ecommerce.db`)
- Single-domain Vercel deployment for web UI and API

## Repository Structure

- `src/` React + Vite role-routed web app
- `backend/` Flask API, models, seed import command, tests
- `api/index.py` Vercel serverless entrypoint for the Flask API
- `scripts/vercel-build.mjs` builds the web app and copies `dist/` to `public/`
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
copy .env.example .env
cmd /c npm install
cmd /c npm run dev
```

Open: `http://localhost:5173`

## Vercel Deploy

- Root Directory: `./`
- Build Command: `npm run vercel-build`
- Install Command: `HUSKY=0 npm ci`
- Output Directory: leave empty/default
- Environment variables: `MONGODB_URI`, `MONGODB_DB`, `AUTH_SECRET`

The same Vercel domain serves the app and API. Browser requests use same-origin `/api/v1`, `/api/*` routes are handled by `api/index.py`, and client routes like `/login` or `/home` fall back to the Vite app.

## Docker

Build and run the full app in one container:

```bash
docker compose up --build
```

Then open `http://localhost:5000`.

The container builds the React app and serves it from Flask. The backend runs in Mongo-only mode.

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
- `seed-import` uses staging tables and idempotent upsert logic.
