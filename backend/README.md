# ERP Backend — Django + DRF

Django port of the Domestic Logistics FRD backend. SQLite by default, zero
external services needed to run it.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- API base: **http://127.0.0.1:8000/api/v1**
- Django admin: **http://127.0.0.1:8000/admin/** (log in with the superuser
  you just created)

There's no Swagger/OpenAPI docs page out of the box like FastAPI's `/docs` —
add `drf-spectacular` if you want one (not included here, to keep the
comparison honest: this is what each framework gives you by default).

## Demo script

1. Register a user: `POST /api/v1/auth/register` with
   `{"email": "...", "full_name": "...", "password": "...", "role": "admin"}`
2. Log in: `POST /api/v1/auth/login` → copy the `access_token`
3. Create a vendor: `POST /api/v1/vendors/` (needs the `Authorization: Bearer <token>` header)
4. Create an order: `POST /api/v1/orders/` — this is Milestone 1
5. Walk it forward: `POST /api/v1/orders/{id}/book`, then
   `POST /api/v1/orders/{id}/advance` repeatedly
6. Add a driver (`POST /api/v1/fleet/drivers`), set their location
   (`PATCH /api/v1/fleet/drivers/{id}/location`), then
   `POST /api/v1/dispatch/orders/{id}/assign` to auto-assign the nearest one
7. `POST /api/v1/orders/{id}/delivery-attempt` with
   `{"success": true, "proof_type": "otp"}`
8. `POST /api/v1/orders/{id}/close-billing?freight_charge=1200`
9. `GET /api/v1/orders/{id}/invoice.pdf` — opens the real invoice PDF inline (viewable in the browser; the user can then save it from there)
10. Exception path: on a different order, call `delivery-attempt` with
    `{"success": false}` three times in a row — the fourth failure
    auto-triggers RTO
11. `GET /api/v1/orders/track/{tracking_number}` — public, no auth needed

Or just do all of this through the React frontend instead of curl/Postman —
it's wired to every one of these endpoints already.

## Endpoint map

| Endpoint | What it does |
|---|---|
| `POST /auth/register`, `/auth/login`, `/auth/me` | Auth |
| `GET/POST /vendors/` | Vendors |
| `GET/POST /fleet/drivers`, `PATCH /fleet/drivers/{id}/location`, `GET/POST /fleet/vehicles` | Fleet |
| `GET/POST /inventory/warehouses`, `GET/POST /inventory/items`, `PATCH /inventory/items/{id}/stock` | Inventory |
| `GET/POST /orders/`, `GET /orders/{id}`, `GET /orders/track/{tracking_number}` | Orders — read/create |
| `POST /orders/{id}/book`, `/advance`, `/delivery-attempt`, `/reattempt`, `/rto`, `/close-billing` | Orders — lifecycle |
| `GET /orders/{id}/invoice.pdf` | Freight invoice PDF |
| `POST /dispatch/orders/{id}/assign` | Nearest-driver assignment |
| `GET /dashboard/stats` | Dashboard aggregates |

### Invoice endpoints (Accounting module)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/invoices/` | Paginated (50, max 100), filter / search / sort. admin+dispatcher: all, vendor: own, driver: 403 |
| GET | `/api/v1/invoices/{id}/` | Detail + e-mail delivery history |
| GET | `/api/v1/invoices/{id}/pdf/` | PDF from the stored invoice (`?download=1` to force download) |
| POST | `/api/v1/invoices/{id}/send-email/` | Admin only — re-queue the invoice e-mail |
| GET | `/api/v1/orders/{id}/invoice.pdf` | Existing URL; now authenticated + permission-checked |
| POST | `/api/v1/orders/{id}/close-billing` | Now admin/dispatcher only; creates the Invoice (optional `tax_amount`) |

Run the tests with `python manage.py test invoices`. Full details (Celery/Redis/e-mail
setup, env vars, permission matrix, examples): see `../INVOICE_MODULE.md`.

