# Backend

Clean FastAPI and MongoDB application using PyMongo's asynchronous API.

## Local setup

```powershell
cd packages/backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Keep the real MongoDB URI in `.env`; never commit it.

## Run

```powershell
python -m uvicorn app.main:app --reload
```

- API documentation: `http://localhost:8000/docs`
- Liveness: `http://localhost:8000/api/v1/health/live`
- MongoDB readiness: `http://localhost:8000/api/v1/health/ready`

## Core API

- `POST /api/v1/auth/register/customer`
- `POST /api/v1/auth/register/provider`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/providers/me`
- `GET /api/v1/providers/me`
- `GET /api/v1/providers/{provider_id}`
- `POST /api/v1/service-requests`
- `GET /api/v1/service-requests/me`
- `GET /api/v1/service-requests/{request_id}`

Provider and service-request field names intentionally match the Component 1 research datasets.

## Test

```powershell
python -m pytest
```

Verify the configured MongoDB connection and required indexes without starting the API:

```powershell
python scripts/verify_database.py
```
