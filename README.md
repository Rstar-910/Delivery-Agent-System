# Delivery Agent System

A C++ console application that simulates a delivery management workflow for three roles:
- **Customer**: place, track, cancel, reschedule, and view past orders
- **Courier Service**: register courier details and update delivery status
- **Admin**: generate delivery reports from stored order records

The project uses a normalised **SQLite-backed** storage layer and exposes both a
menu-driven terminal interface (C++) and a **FastAPI REST API** (Python) over the
same database file — a multi-language system sharing a common persistence layer.

---

## Resume Highlights

- Designed and implemented a **role-based logistics workflow** (Customer, Courier, Admin) using modular C++ components.
- Built a reusable **order data model** and SQLite persistence utilities for consistent storage, retrieval, and updates.
- Added **input validation and state-aware business rules** (cancel, reschedule, status update) to improve reliability.
- Implemented **admin analytics reporting** with status-wise summaries for operational visibility.
- **Exposed the system via a FastAPI REST API**, sharing the same SQLite persistence layer as the C++ console app — enabling programmatic access alongside the existing terminal interface.
- Implemented **role-based access control (RBAC)** with bcrypt-hashed credentials and SQLite-backed sessions (restart-safe, 24 h TTL).
- Improved **cross-platform compatibility** by removing non-portable dependencies and standardising build steps.

---

## Project Structure

```
Delivery-Agent-Sysytem/
├── Source/
│   ├── main.cpp            — entry point and role-based menus (C++ console app)
│   ├── customer.cpp        — customer workflows
│   ├── courierservice.cpp  — courier service workflows
│   ├── admin.cpp           — admin reporting
│   └── common.cpp          — shared order persistence and console utilities
├── api/
│   ├── main.py             — FastAPI app entry point
│   ├── auth.py             — login/logout endpoints, session management, role guards
│   ├── database.py         — SQLite helpers (WAL mode, schema, connection context)
│   ├── models.py           — Pydantic request/response schemas
│   ├── seed_users.py       — one-time script to create default user accounts
│   └── routers/
│       ├── customer.py     — /orders CRUD (Customer role)
│       ├── courier.py      — /courier/details and /orders/{id}/status (Courier role)
│       └── admin.py        — /admin/report (Admin role)
├── Makefile                — C++ build instructions
├── requirements.txt        — Python dependencies
└── delivery_agent.db       — SQLite database (shared by both interfaces)
```

---

## Features

### Customer
- Book a delivery (name and shipping address)
- View full order details by order ID
- Cancel an order by order ID (status-based cancellation)
- View past records by customer name
- Reschedule an order with updated delivery date

### Courier Service
- Add courier company details and pricing information
- Update order status by order ID (`PickedUp`, `InTransit`, `Delivered`)

### Admin
- Generate a tabular report of all delivery records
- View aggregate status summary (e.g., Booked, InTransit, Delivered)

---

## Data Storage

Both interfaces read from and write to the same file:

- `delivery_agent.db` — SQLite database containing:
   - `orders(order_id, customer_name, address, status, scheduled_date, created_at)`
   - `courier_companies(id, company_name, contact_number, location, packaging_price, discount, created_at)`
   - `users(id, username, password_hash, role, created_at)` ← API layer
   - `sessions(token, user_id, role, created_at, expires_at)` ← API layer

---

## Requirements

### C++ console app
- C++ compiler with C++11 support (`g++` recommended)
- `make`
- SQLite3 development library (`sqlite3` / `libsqlite3-dev`)

### REST API
- Python 3.9+
- `pip install -r requirements.txt`

---

## Build and Run — C++ Console App

```bash
make
./delivery_agent_system
```

---

## Build and Run — REST API

### 1. Install dependencies (first time only)
```bash
pip3 install -r requirements.txt
```

### 2. Seed default users (first time only)
```bash
python3 -m api.seed_users
```

### 3. Start the API server
```bash
uvicorn api.main:app --reload --port 8000
```

### 4. Open the interactive API docs
```
http://localhost:8000/docs
```

---

## REST API Endpoints

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/login` | public | Returns a Bearer token |
| `POST` | `/auth/logout` | Bearer | Revokes the current token |

### Customer (`customer` role required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/orders` | Book a new delivery |
| `GET` | `/orders/{id}` | View order status |
| `DELETE` | `/orders/{id}` | Cancel an order |
| `GET` | `/orders?customer_name=X` | View past records |
| `PATCH` | `/orders/{id}/reschedule` | Reschedule an order |

### Courier (`courier` role required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/courier/details` | Register courier company |
| `PATCH` | `/orders/{id}/status` | Update delivery status |

### Admin (`admin` role required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/report` | Full report + status summary |

### Default credentials

> **Note:** These are demo-only credentials for local development. They are not representative of production security practice — in a real deployment, credentials would be provisioned out-of-band and never committed to source control.

| Username | Password | Role |
|----------|----------|------|
| `customer1` | `pass123` | customer |
| `courier1` | `pass123` | courier |
| `admin1` | `pass123` | admin |

---

## Example curl Walkthrough

```bash
# 1. Login as customer
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"customer1","password":"pass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 2. Book a delivery
curl -s -X POST http://localhost:8000/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"customer_name":"Alice Smith","address":"123 Main St","scheduled_date":"25-12-2025"}'

# 3. View the order (replace 1 with actual order_id)
curl -s http://localhost:8000/orders/1 \
  -H "Authorization: Bearer $TOKEN"

# 4. Verify RBAC: customer token on admin endpoint → 403 Forbidden
curl -s http://localhost:8000/admin/report \
  -H "Authorization: Bearer $TOKEN"

# 5. Get admin report
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin1","password":"pass123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s http://localhost:8000/admin/report \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Architecture Notes

### Two data-access layers
`Source/common.cpp` and `api/database.py` both implement query logic against the
same schema. This is intentional — the C++ console app was preserved intact to
keep the original project's story, while the Python API layer was added without
requiring a rewrite. The SQLite schema is the single source of truth shared between
both layers. In a production system these would converge into one service boundary.

### Concurrent access
Both the C++ app and the FastAPI server can be run simultaneously. SQLite's
**WAL (Write-Ahead Logging)** mode is enabled by the API server on every connection,
allowing concurrent reads while serialising writes safely via file locking.
The API server sets a 10-second write timeout before raising an error. Verified
manually by writing from both interfaces simultaneously.

### CORS policy
The API allows all origins (`allow_origins=["*"]`). This is appropriate for a
local demo project. In production, restrict to the specific frontend origin to
prevent cross-origin token theft.

---

## Usage Flow — C++ Console App

1. Start the program (`./delivery_agent_system`).
2. Choose one role: `1` Customer / `2` Admin / `3` Courier Service / `4` Exit.
3. Follow the menu options shown for the selected role.
4. Use generated **Order ID** values to track, update, or cancel orders.

---

## Clean Build Artifacts

```bash
make clean
```

---

## Future Improvements

- Add stronger input validation and error handling
- Add unit and integration tests for both the C++ and API layers
- Add token refresh endpoint
- Make the build fully cross-platform
- Converge the two data-access layers into a single shared service
