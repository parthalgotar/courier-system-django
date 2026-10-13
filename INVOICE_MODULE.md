# Accounting / Invoice Management Module

This document covers everything added for invoice management: database changes,
APIs, permissions, Celery/Redis/e-mail setup, and how to run and test it.

> Commands are shown for **Windows PowerShell** (matching the rest of this
> project's README). On macOS/Linux use `source .venv/bin/activate` instead of
> `.venv\Scripts\activate`.

---

## 1. Quick start

```powershell
# --- backend ---
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt          # now also installs celery, redis, django-filter
copy .env.example .env
python manage.py migrate                 # creates Invoice tables + backfills already-closed orders
python manage.py createsuperuser
python manage.py runserver

# --- frontend (second terminal) ---
cd frontend
npm install
copy .env.example .env
npm run dev
```

The app works with **no extra services**. Invoice e-mails are queued to Celery;
if Redis is not running, billing still succeeds and the e-mail is recorded as
`failed` (see section 7). To actually deliver e-mail in development, pick one:

| I want…                                   | Do this |
|-------------------------------------------|---------|
| Nothing extra (just try the UI)           | Nothing. Billing works; e-mail shows `failed` in the invoice's history. |
| E-mails sent inline, **no Redis**         | Put `CELERY_TASK_ALWAYS_EAGER=True` in `backend/.env`. E-mails are printed to the runserver console. |
| The real async setup                      | Follow section 5 (Redis + Celery worker). |

### Giving a role a working login
* Register users from the app's Register page (choose a role), or in `/admin/`.
* A Django **superuser** gets the default role `dispatcher` — open the user in
  `/admin/` and set **Role = admin** to see admin-level invoice access.
* **Link a vendor to a login:** `/admin/` → **Vendors** → open the vendor → set
  **User** (and optionally **Email**, used when there is no linked user).
  Until a vendor is linked, no vendor account can see that vendor's invoices.

---

## 2. Database changes

| Model / change | Details |
|---|---|
| `invoices.Invoice` (new) | `order` (FK, `PROTECT`), `invoice_number` (unique), `invoice_date`, `freight_charge`, `tax_amount`, `cod_amount`, `total_amount`, `status` (`draft`/`issued`/`paid`/`cancelled`), `created_by` (FK→User, `SET_NULL`), `created_at` |
| `invoices.InvoiceSendLog` (new) | `invoice` (FK, `CASCADE`), `recipient_email`, `sent_at`, `status` (`pending`/`sent`/`failed`/`bounced`), plus `error_message`, `attempts`, `created_at` |
| `vendors.Vendor.user` (new) | Nullable `OneToOneField` → User. Decides which invoices a vendor account owns. |
| `vendors.Vendor.email` (new) | Optional fallback billing e-mail when the vendor has no linked user. |

**Deliberate deviations from the PDF's sample model** (all permitted by its notes):

* Money uses `DecimalField(12, 2)` instead of `FloatField`, so totals are exact.
* An extra `cod_amount` column snapshots the COD amount included in the total
  (existing billing rule: `total = freight + COD`, and now `+ tax`), so the PDF
  can be rebuilt purely from the invoice row.
* `InvoiceSendLog.recipient_email` allows blank so a "vendor has no e-mail"
  failure can still be logged.

**Database-level guarantees**
* `uniq_active_invoice_per_order`: an order can have at most **one non-cancelled invoice**. A
  cancelled invoice does not block re-billing (the new number gets a `-2` suffix).
* `CHECK` constraints: freight, tax, COD and total are all `>= 0`.

**Migrations**
* `vendors/0002_vendor_user_email`, `invoices/0001_initial`
* `invoices/0002_backfill_closed_orders` — creates an `issued` Invoice for every
  order that was already `closed` before this module, restoring its original
  invoice number, amounts and billing time. Safe to re-run; no-op on rollback.

---

## 3. Billing integration

`POST /api/v1/orders/{id}/close-billing?freight_charge=1200[&tax_amount=180.50]`

* Same URL, same response body, same error messages as before (`409` if the order
  is not Delivered, `422` if `freight_charge` is missing/invalid).
* New: optional `tax_amount` (default `0`); negative / `NaN` values are rejected with `422`.
* Order close + invoice creation happen in **one transaction**.
* **Duplicate protection (three layers):** status re-check under a row lock,
  an idempotent `create_invoice_for_order()`, and the database's partial unique
  constraint. A retry returns `409` (as before) and never creates a second invoice.
* Invoice number: `ORD-1A2B3C4D` → `INV-1A2B3C4D` (unchanged scheme).
* The invoice e-mail is queued **after commit** and can never break billing.
* **Now requires authentication and role admin or dispatcher** (it was open to
  everyone before). The React app already sent the token.

---

## 4. API reference

Base URL `http://127.0.0.1:8000/api/v1`. All endpoints need
`Authorization: Bearer <access_token>` (from `POST /auth/login`).

### `GET /invoices/`
Paginated list. Query parameters:

| Param | Meaning |
|---|---|
| `page`, `page_size` | Default page size **50**, max **100** (`?page_size=100000` returns 100). |
| `status` | `draft` \| `issued` \| `paid` \| `cancelled` |
| `search` | Matches invoice #, order #, tracking #, customer name, vendor name |
| `invoice_number`, `order_number`, `tracking_number`, `customer_name` | Case-insensitive "contains" |
| `vendor` | Vendor id (staff only; vendors are already limited to their own) |
| `created_after`, `created_before` | `YYYY-MM-DD`, inclusive |
| `min_total`, `max_total` | Numeric range on `total_amount` |
| `sort_by` + `order` | e.g. `sort_by=total_amount&order=desc`. Fields: `invoice_date`, `created_at`, `total_amount`, `freight_charge`, `invoice_number`, `status`. Standard `?ordering=-total_amount` also works. Default: newest first. |

Invalid values (e.g. `status=bogus`, `created_after=nope`) return `400` with a
per-field message. Unknown sort fields are ignored. `page=0` or a page past the
end returns `404`.

```json
GET /api/v1/invoices/?status=issued&sort_by=total_amount&order=desc&page_size=2

{
  "count": 25,
  "next": "http://127.0.0.1:8000/api/v1/invoices/?order=desc&page=2&page_size=2&sort_by=total_amount&status=issued",
  "previous": null,
  "results": [
    {
      "id": 2,
      "invoice_number": "INV-17D49189",
      "order_id": 2,
      "order_number": "ORD-17D49189",
      "tracking_number": "B634078376",
      "customer_name": "John Doe",
      "vendor_id": 1,
      "vendor_name": "Alpha Traders",
      "invoice_date": "2026-09-24T07:46:45.245031Z",
      "freight_charge": "800.75",
      "tax_amount": "0.00",
      "cod_amount": "500.00",
      "total_amount": "1300.75",
      "status": "issued",
      "status_display": "Issued",
      "created_at": "2026-09-24T07:46:45.245064Z"
    }
  ]
}
```
Amounts are JSON **strings** (decimal-safe).

### `GET /invoices/{id}/`
Same fields plus `order`, `vendor`, `created_by_name` and `send_logs`
(e-mail delivery history; `error_message` is included for admin/dispatcher only).

```json
{
  "id": 2, "invoice_number": "INV-17D49189", "total_amount": "1300.75", "status": "issued",
  "order":  { "id": 2, "order_number": "ORD-17D49189", "status": "closed", "customer_name": "John Doe",
              "origin_city": "Pune", "destination_city": "Mumbai", "commodity": "Cartons", "weight_kg": 40.0, "is_cod": true },
  "vendor": { "id": 1, "name": "Alpha Traders", "address": "1 Alpha Rd, Pune", "contact_phone": "9000000001" },
  "created_by_name": "Admin",
  "send_logs": [
    { "id": 2, "recipient_email": "vendora@erp.com", "status": "sent",
      "sent_at": "2026-09-24T07:46:45.302880Z", "attempts": 1, "error_message": "", "created_at": "2026-09-24T07:46:45.251411Z" }
  ]
}
```
*(fields abbreviated in this example)*

### `GET /invoices/{id}/pdf/`
Returns the invoice PDF generated from the stored record.
`?download=1` sends `Content-Disposition: attachment` (default is `inline`).

### `GET /orders/{order_id}/invoice.pdf`  *(existing URL, updated)*
Now authenticated; loads the stored Invoice and renders the same PDF; same
permission rules. `409` if the order isn't closed yet, `404` if a closed order has no invoice record.

### `POST /invoices/{id}/send-email/`  *(admin only)*
Queues another e-mail to the vendor (e.g. after a `failed` attempt). Returns
`202` with the new pending log. Only `issued`/`paid` invoices (`409` otherwise).

### Status codes
`401` no/invalid token · `403` role or ownership not allowed · `404` unknown id · `409` wrong state · `422` bad billing input.

---

## 5. Full ERP Permission Matrix

| Operation / Endpoint | Admin | Dispatcher | Vendor | Driver | Anonymous |
|---|:--:|:--:|:--:|:--:|:--:|
| **Orders** (`/api/v1/orders/`) | | | | | |
| List orders | All | All | **Own orders only** | **Assigned orders only** | ❌ 401 |
| Create order | ✅ | ✅ | ✅ (forced to own vendor) | ❌ 403 | ❌ 401 |
| View order detail | All | All | Own orders only | Assigned orders only | ❌ 401 |
| Advance milestone / actions | ✅ | ✅ | ❌ 403 | Assigned only (delivery attempt) | ❌ 401 |
| Public track shipment | ✅ (safe) | ✅ (safe) | ✅ (safe) | ✅ (safe) | ✅ (safe redacted) |
| **Invoices** (`/api/v1/invoices/`) | | | | | |
| List invoices | All | All | **Own only** | ❌ 403 | ❌ 401 |
| View invoice detail | All | All | Own only | ❌ 403 | ❌ 401 |
| Download / view PDF | All | All | Own only | ❌ 403 | ❌ 401 |
| Close & bill an order | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 401 |
| Update invoice status | ✅ (issued/paid/cancel)| ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| Re-send invoice e-mail | ✅ | ❌ 403 (read-only) | ❌ 403 | ❌ 403 | ❌ 401 |
| Delete invoice | ❌ 400 if closed | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **Vendors** (`/api/v1/vendors/`) | | | | | |
| List vendors | All | All | Own vendor only | ❌ 403 | ❌ 401 |
| Create vendor | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| Link user to vendor (`link_user`) | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| **Fleet & Drivers** (`/api/v1/fleet/`) | | | | | |
| List drivers | All | All | ❌ 403 | **Own driver profile only** | ❌ 401 |
| Create driver | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 401 |
| Update GPS location | ✅ | ✅ | ❌ 403 | **Own GPS location only** | ❌ 401 |
| **Inventory** (`/api/v1/inventory/`) | | | | | |
| Warehouses & items list | All | All | View items only | ❌ 403 | ❌ 401 |
| Create warehouse / item | ✅ | ✅ | ❌ 403 | ❌ 403 | ❌ 401 |
| **Dashboard** (`/api/v1/dashboard/stats`) | All stats | All stats | **Own stats only** | **Own stats only** | ❌ 401 |
| **Notifications** (`/api/v1/notifications/`)| All logs | All logs | Own order logs | Assigned order logs | ❌ 401 |
| **Auth / Registration** (`/api/v1/auth/register/`) | — | — | Low privilege only (No Admin) | Low privilege only | Public (No Admin) |

### Object-level Isolation & Data Integrity
* **Vendors**: Scoped at database SQL level to `user=request.user`. Detail routes enforce `403` on any other vendor's record.
* **Drivers**: Linked via `Driver.user` (`OneToOneField`). Orders scoped to `driver__user=request.user`. Drivers can only view/update their own location.
* **Global DRF Default**: `REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = ("rest_framework.permissions.IsAuthenticated",)`. Anonymous access is blocked globally except explicitly whitelisted public endpoints (`/auth/login`, `/auth/register`, `/orders/track/<tracking_number>`).
* **Public Track Trimming**: `/orders/track/<tracking_number>` exposes only milestone status, origin city, destination city, and timeline. It does **not** expose internal billing, freight charges, customer phone numbers, or delivery addresses.

---

## 5.1 Milestone Notifications System

Automatic notifications are triggered upon milestone state transitions:

### Supported Triggers & Matrix
1. **`order_received`**: Vendor Email ("Order Confirmed & Picked Up").
2. **`booking_planned`**: Vendor Email ("Linehaul Booking Scheduled").
3. **`out_for_delivery`**: Customer SMS & Email ("Out for Delivery with Driver details").
4. **`delivery_attempted`**: Dispatcher Email ("Delivery Attempt Recorded").
5. **`delivery_failed`**: Customer SMS & Dispatcher Email ("Delivery Attempt Failed").
6. **`reattempt` / `reattempt_scheduled`**: Transitions order back to `out_for_delivery`, re-triggering delivery notification.
7. **`delivered` / `closed`**: Customer SMS & Email + Vendor Invoice Email.

### Notification Model (`notifications/models.py`)
* `order`: ForeignKey to `orders.Order`.
* `event`: ForeignKey to `orders.OrderEvent` (enables distinct notification records for repeated events like reattempts).
* `order_status`: Milestone status at time of notification.
* `channel`: `email`, `sms`, or `both`.
* `recipient_type`: `customer`, `vendor`, or `dispatcher`.
* `recipient_email`: Recipient e-mail address.
* `recipient_phone`: Recipient phone number.
* `subject`: Message subject.
* `message`: Enriched message body (includes driver name, phone, order weight, delivery address, slot).
* `status`: `pending`, `sent`, `failed`, or `skipped`.
* `attempts`: Retry counter.
* `error_message`: Error details upon delivery failure.
* `sent_at`: Timestamp when provider accepted delivery.
* `created_at`: Creation timestamp.

---

## 6. Celery, Redis and e-mail setup

Invoice e-mails are sent by a Celery task (`invoices.tasks.send_invoice_email`)
so billing never waits on SMTP. Redis is the broker.

### Redis
* **Windows:** Redis has no official Windows build. Easiest options: **Docker**
  (`docker run -p 6379:6379 redis`), **WSL2** (`sudo apt install redis-server && redis-server`), or Memurai.
* **macOS:** `brew install redis && redis-server`   **Linux:** `sudo apt install redis-server && redis-server`

### Celery worker
```powershell
cd backend
.venv\Scripts\activate
celery -A config worker -l info --pool=solo      # Windows needs --pool=solo
# macOS / Linux:  celery -A config worker -l info
```
Keep it running alongside `runserver`. (`django-celery-beat` / Celery Beat are **not** needed for invoices.)

### E-mail provider
By default e-mails are printed to the console. For real delivery add to `backend/.env`
(example: SendGrid):
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
SENDGRID_API_KEY=SG.xxxxxxxx
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```
Any SMTP provider works the same way. **Never commit real keys** — `.env` is git-ignored.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Configured but unused (results are ignored on purpose, see below) |
| `CELERY_TASK_ALWAYS_EAGER` | `False` | `True` = run tasks inline, no Redis/worker (dev only) |
| `EMAIL_BACKEND` | console backend | Set to the SMTP backend for real delivery |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_USE_TLS` | `smtp.sendgrid.net` / `587` / `True` | SMTP server |
| `EMAIL_HOST_USER` | `apikey` | SMTP user |
| `EMAIL_HOST_PASSWORD` or `SENDGRID_API_KEY` | empty | SMTP password / SendGrid key |
| `DEFAULT_FROM_EMAIL` | `noreply@erpsystem.com` | From address |

### How delivery behaves
1. Billing creates a `pending` `InvoiceSendLog` and, after the DB commit, queues the task.
2. The worker builds the PDF from the invoice, e-mails it, then sets `sent` + `sent_at`.
3. SMTP error → up to **3 retries** (1, 2, 4 min back-off), log stays `pending` with the error; after that → `failed`.
4. Vendor has no e-mail → logged as `failed` ("no registered e-mail address"); billing unaffected.
5. Redis down → `.delay()` fails in well under a second, log becomes `failed`, billing returns `200`.
   Fix Redis, then an admin can use **Re-send e-mail**.
6. A log already `sent` is never sent twice (safe against broker redelivery).

Task results are ignored (`CELERY_TASK_IGNORE_RESULT`) on purpose: delivery state
lives in `InvoiceSendLog`. Without this, `.delay()` blocks ~20 s when Redis is down.

`bounced` exists as a status for future use (a provider bounce webhook would set
it); nothing sets it automatically yet.

---

## 7. Frontend

New pages (same look and feel as the existing console):

* **Invoices** (`/invoices`) — search, status, vendor (staff), date range, sort, page-size,
  Previous/Next with "Page X of Y · N invoices", per-row PDF download, loading / empty / error / no-access states.
* **Invoice detail** (`/invoices/:id`) — charges, order & vendor info, e-mail delivery history,
  View/Download PDF, Re-send e-mail (admin).
* **Sidebar** shows *Invoices* only to admin / dispatcher / vendor. Drivers see no link, and the route shows "no access".
* **Order drawer (existing screen)** — the "View" button redirects directly to the
  associated Invoice Detail Page (`/invoices/:id`). If no invoice exists for the order, a clear message is displayed. Billing button shows only to admin/dispatcher.
* `AuthContext` now also holds the user's `role` (from `/auth/me`) and signs out if the token is rejected.

---

## 8. Testing

**Backend (74 tests, no Redis/SMTP needed):**
```powershell
cd backend
python manage.py test invoices
```
Covers: model constraints; billing creates an invoice; retry/duplicate prevention;
legacy validation messages; RBAC for all four roles + anonymous + bad token;
vendor isolation by ID; pagination (`page_size` 1/50/100/100000, invalid pages, stable ordering);
filters, search, sorting, invalid values; PDF contents vs. DB record; e-mail success, failure, retry,
no-recipient, broker-down, after-commit queuing; and the backfill migration.

**Manual check of the async path**
1. Start Redis + worker (section 6) and `runserver`.
2. Link a vendor to a user with an e-mail (section 1), drive an order to *Delivered*, click **Close & generate invoice**.
3. Open **Invoices → that invoice**: the e-mail history shows `sent` (and the mail arrives / prints in the worker console).

---

## 9. Implementation & Audit Status: 100% Complete

All requirements previously marked as 🟡 PARTIALLY COMPLETED in the ERP Requirement Audit have been implemented and verified:

1. **Role-Based Access Control (RBAC) & Security Hardening (✅ 100% Complete)**:
   * Global DRF default set to `IsAuthenticated` (no unauthorized access).
   * Public registration `/auth/register` locked down: strictly rejects `admin` role requests and defaults to low-privilege roles.
   * `Driver.user` OneToOne link added with migrations and Django admin integration.
   * Scoped order lists, order permissions, driver fleet lists, and driver GPS location updates to assigned driver only (`_get_linked_driver`).
   * Driver dashboard enabled for assigned driver orders only.
   * Vendor orders: vendors can create orders forced to their own vendor ID.
   * Vendor creation restricted to Administrators (dispatchers get 403).
   * Vendor-to-user linking API added (`/api/v1/vendors/<id>/link_user/`) for linking outside Django admin.
   * Public tracking route `/orders/track/<tracking_number>` trimmed to expose public tracking data only without leaking sensitive billing or customer data.
   * Invoice deletion restricted: invoices for closed orders cannot be deleted (returns 400).

2. **Global Pagination & Search Filtering (✅ 100% Complete)**:
   * `StandardPagination` (`page_size=50`, `max_page_size=100`) enabled globally via `DEFAULT_PAGINATION_CLASS` and applied across Orders, Invoices, Vendors, Fleet Drivers, Vehicles, Warehouses, Inventory Items, and Notifications.
   * React UI across all modules updated to unpack pagination envelopes (`res.results || res`).
   * Orders list UI enhanced with a dynamic Sort By dropdown (`created_at`, `order_number`, `customer_name`, `weight_kg`, `declared_value`), direction toggle (ASC/DESC), and explicit tracking number search filter.

3. **Milestone Notifications & Celery/SMS/Email Delivery (✅ 100% Complete)**:
   * `Notification` model fully aligned with all audit requirements: `order`, `event`, `order_status`, `channel` (email, sms, both), `recipient_type`, `recipient_email`, `recipient_phone`, `subject`, `message`, `status`, `attempts`, `error_message`, `sent_at`, `created_at`.
   * All 7 milestone triggers active; reattempt endpoint triggers `out_for_delivery` notifications.
   * Deduplication keyed by `(order, event, channel)` so repeated transitions (e.g. consecutive failed delivery attempts) each generate distinct notification records.
   * Rich message templates populated with driver name, driver phone, package weight, delivery address, and pickup slot.
   * Customer email field added to `Order` model and UI forms.
   * Broker queueing failure handling: records a failed notification row if Celery broker is unreachable.
   * Twilio SMS backend support with `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` (and `SMS_*` aliases).
   * Dedicated Notification APIs (`/api/v1/notifications/`, `/api/v1/orders/<id>/notifications`) and real-time live dispatch feedback in the React `OrderDrawer`.
