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

## Test

```powershell
python -m pytest
```
