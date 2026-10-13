# ERP System — Django Edition (Backend + Frontend)

This is the **Django port** of the ERP system — same database design, same
14-milestone Domestic Logistics FRD flow, same API shape, so the **exact same
React frontend** (copied over unmodified) works against it.

```
erp_system/
├── backend/     ← Django + Django REST Framework — the API, database, business logic
└── frontend/    ← React + Vite + Tailwind — the console UI (unchanged)
```

## Running both together

Open **two terminals**.

**Terminal 1 — backend:**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Runs on **http://127.0.0.1:8000** — Django admin at `/admin/`.

**Terminal 2 — frontend:**
```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```
Runs on **http://127.0.0.1:5173** — this is the app you use in the browser.

Leave both terminals running while you work.

## Accounting / Invoice Management

Closing & billing an order now creates a persistent **Invoice**, with invoice
list/detail APIs, role-based access (admin / dispatcher / vendor-own / no driver),
invoice PDFs generated from the stored record, and asynchronous invoice e-mail
via Celery + Redis with a delivery log. The React console has new **Invoices** pages.

Setup, API reference, permission matrix, Celery/Redis/e-mail configuration and
testing are in **[INVOICE_MODULE.md](INVOICE_MODULE.md)**.

> `pip install -r backend/requirements.txt` again after pulling this update
> (new: `celery`, `redis`, `django-filter`), then run `python manage.py migrate`.

## What's different from the FastAPI version

- **Auth**: `djangorestframework-simplejwt` instead of `python-jose` — same
  `{access_token, token_type}` response shape, so the frontend needed zero
  changes.
- **ORM**: Django's built-in ORM (synchronous) instead of SQLAlchemy 2.0 async
  — no `async`/`await` anywhere in this backend; Django handles the
  request/response cycle synchronously by default.
- **Admin**: Django ships a full CRUD admin site for free — visit `/admin/`
  after creating a superuser to see every model (Orders, Vendors, Drivers,
  Inventory) with add/edit/delete screens and the full milestone/document
  trail inline on each order, with zero extra frontend code.
- **Validation**: Django REST Framework serializers instead of Pydantic
  schemas — same job (validate request/response shape), different syntax.
- **Structure**: six small Django "apps" (`accounts`, `vendors`, `fleet`,
  `inventory`, `orders`, `dispatch`, `dashboard`) instead of FastAPI's
  `models/ schemas/ api/` folders — Django groups by feature, FastAPI grouped
  by layer.

See `backend/README.md` for the full endpoint list and demo script (same
as the FastAPI version — try creating an order, walking it through
milestones, and downloading the invoice PDF).

A **FastAPI vs Django comparison document** is included separately —
use it to explain the two approaches side by side.
