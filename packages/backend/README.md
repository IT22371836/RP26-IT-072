# Firebase-only FastAPI backend

FastAPI runs the Component 1 and Component 4 Python/ML models and exposes the
pipeline API. Firebase Authentication is the only authentication system and
Firebase Realtime Database is the only runtime database. Component 2 continues
to use its existing `filter_requests` RTDB contract.

MongoDB is not connected by FastAPI or the pipeline worker. The optional
`migration` dependency and `migrate_mongodb_to_firebase.py` script exist only
to verify or repeat the one-time historical migration.

## Local setup

```powershell
cd packages/backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Configure `FIREBASE_PROJECT_ID`, `FIREBASE_DATABASE_URL`, and a service-account
path outside Git. Never commit the Admin SDK JSON.

## Run FastAPI

From the repository root:

```powershell
.\scripts\windows\start-fastapi.ps1 -Port 8001
```

Or from `packages/backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

## Run the pipeline worker

```powershell
cd packages/backend
.\.venv\Scripts\python.exe -m app.pipeline.worker
```

The API and worker both use Firebase Admin SDK. Run exactly one worker initially.

## Health

- Liveness: `http://127.0.0.1:8001/api/v1/health/live`
- Firebase readiness: `http://127.0.0.1:8001/api/v1/health/ready`
- API docs: `http://127.0.0.1:8001/docs`

## Firebase data ownership

- `core/users`, `core/customer_profiles`, `core/provider_verification_events`
- `component1/service_requests`, `component1/interactions`
- `component1/runs`, `component1/provider_scores`
- `component4/runs`, `component4/provider_scores`
- `pipeline/runs`, `pipeline/workers`, `pipeline/idempotency`
- Existing `customers`, `providers`, `filter_requests`, `daily_demand`, and
  research review nodes remain compatible.

The backend namespaces are Admin-only in RTDB rules. Browser authentication and
profile ownership continue to use Firebase Authentication and UID-scoped rules.

## Historical migration verification

Install the optional migration dependency only on the migration workstation:

```powershell
python -m pip install -e ".[migration]"
python scripts\migrate_mongodb_to_firebase.py --verify-only `
  --mongo-uri "<atlas-uri>" --mongo-database "<database>" `
  --report ..\..\docs\integration\mongodb-to-firebase-post-verify.json
```

The migration is additive, excludes password hashes, preserves existing
Firebase values, and verifies that Component 2 data was not changed.
