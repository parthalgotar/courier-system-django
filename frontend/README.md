# ERP Console — React Frontend (Vite + Tailwind)

A console-style frontend for the FastAPI ERP backend: register/login, manage
vendors (first-mile pickup points), place and advance orders through the
delivery lifecycle, and manage your driver fleet — all against the real API.

## Setup

Make sure the FastAPI backend is already running (see the backend's own
README) — by default at `http://127.0.0.1:8000`.

```bash
# 1. Install dependencies
npm install

# 2. Copy environment file and point it at your backend
cp .env.example .env
# .env contains: VITE_API_URL=http://127.0.0.1:8000/api/v1

# 3. Run the dev server
npm run dev
```

Open **http://127.0.0.1:5173**.

## Important — backend CORS

The FastAPI backend needs CORS enabled for this frontend's origin
(`http://localhost:5173`). This is already configured in the backend's
`app/main.py` via `CORSMiddleware` — if you changed the frontend's port,
add it to the `allow_origins` list in the backend too.

## What's included

| Page | What it does |
|---|---|
| `/login`, `/register` | Auth against `/api/v1/auth` — stores the JWT in `localStorage` |
| `/` (Dashboard) | Quick counts: total orders, in-transit, vendors, drivers |
| `/vendors` | Add and list first-mile pickup vendors |
| `/orders` | Create orders, and step them through the lifecycle: created → picked up → at hub → dispatch (auto-assigns nearest available driver) → delivered |
| `/fleet` | Add drivers and update their live lat/lng (used by the dispatch auto-assign logic) |

## Design notes

Built as an operations console rather than a marketing page: dark sidebar,
paper-white content area, freight-green accent, monospace for order numbers
and coordinates. The signature element is the horizontal status timeline on
each order card — a checkpoint-style progress line through the first-mile →
hub → last-mile flow, similar to a shipping manifest scan log.

## Folder structure

```
src/
├── api/client.js          # fetch wrapper for all backend calls
├── context/AuthContext.jsx # JWT storage + login/register/logout
├── components/
│   ├── Sidebar.jsx, Layout.jsx
│   ├── StatusTimeline.jsx  # signature order-progress component
│   └── ui.jsx              # Button, Input, Card, EmptyState, etc.
└── pages/
    ├── Login.jsx, Register.jsx
    ├── Dashboard.jsx, Orders.jsx, Vendors.jsx, Fleet.jsx
```

## Next steps you might want

- Real-time order/driver updates via WebSocket or SSE instead of manual refresh
- Map view for vendor/driver/delivery locations (e.g. Leaflet or Mapbox GL)
- Pagination once order/vendor lists grow large
