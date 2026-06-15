# AI-Powered Eyewear Order Management System

Full-stack Order Management System for an eyewear brand, built according to the provided architecture plan.

## Tech Stack

- **Frontend:** Next.js 16 + TypeScript + Tailwind CSS + Recharts + Lucide
- **Backend:** FastAPI + SQLAlchemy + Pydantic + JWT
- **Database:** SQLite (default) — swap `DATABASE_URL` in `backend/.env` to use PostgreSQL
- **AI Layer:** Rule-based prediction engine + Kimi-style natural language explanations

## Features Implemented

1. **Inventory Intelligence**
   - Lens inventory tracking with power, type, index, coating
   - Demand forecasting & restock/overstock recommendations
   - One-click procurement simulation

2. **Order Management**
   - Create orders, lifecycle status tracking, status timeline
   - Filters by status, lens type, store location
   - Delay reason logging

3. **SLA Breach Prediction**
   - Risk score based on lens type, coating, index, inventory, stage, location, historical breaches
   - Predicted completion hours and expected delay
   - Breach flagging

4. **AI Explanation Layer**
   - Human-readable explanations for risk and delays
   - Powered by a deterministic prediction engine (Kimi API integration point documented)

5. **Executive Dashboard**
   - KPI cards: total orders, orders at risk, SLA breaches, inventory health, forecast accuracy, procurement
   - AI Risk Center table
   - Order status distribution chart
   - Inventory intelligence preview

6. **Authentication & RBAC**
   - JWT login
   - Roles: admin, operations_manager, qc_manager

## Project Structure

```
backend/
  app/
    main.py
    models.py
    schemas.py
    auth.py
    dependencies.py
    database.py
    config.py
    seed.py
    routers/       # auth, orders, inventory, dashboard, ai
    services/      # prediction engine
  requirements.txt
  run.py
frontend/
  app/             # pages: login, dashboard, orders, inventory, risk
  components/      # sidebar, kpi-card
  lib/             # api, auth context
```

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend will seed demo users, inventory, and orders on startup.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Demo Credentials

| Email              | Password  | Role                  |
|--------------------|-----------|-----------------------|
| admin@eluno.com    | admin123  | Admin                 |
| ops@eluno.com      | ops123    | Operations Manager    |
| qc@eluno.com       | qc123     | QC Manager            |

## Key API Endpoints

- `POST /api/auth/login`
- `GET /api/orders`
- `PATCH /api/orders/{id}/status`
- `GET /api/inventory`
- `GET /api/dashboard`
- `POST /api/ai/explain-risk`
- `GET /api/ai/forecast`

## AI / Kimi Integration Notes

The current AI layer is implemented as a deterministic analytics and prediction engine so the system runs immediately without external API keys. To wire a real Kimi/generative AI model:

1. Add an async HTTP client (e.g., `httpx`) to `backend/requirements.txt`.
2. Replace `app/services/prediction.py::generate_explanation` with a call to the Kimi completions API.
3. Pass the order features and predicted risk to the model and return the generated text.

The schema and frontend already expect a plain-text explanation string.

Author

Bhuvan Kambad

bkambad041@gmail.com
