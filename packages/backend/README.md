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
- `POST /api/v1/component4/rank`
- `GET /api/v1/component4/runs/{run_id}`
- `GET /api/v1/component4/models`
- `GET /api/v1/component4/integration-readiness`
- `GET /api/v1/component4/release-readiness`
- `GET /api/v1/component4/handoff-readiness`
- `GET /api/v1/component4/final-readiness`
- `GET /api/v1/component4/runtime-metrics` (administrator only)
- `GET /api/v1/component4/weights/{category}`
- `GET /api/v1/component4/health`

Provider and service-request field names intentionally match the Component 1 research datasets.

Component 4 accepts one to ten unique provider IDs from the previous pipeline stage and
returns at most five deterministic CATF-ranked providers. The ranking endpoint requires a
customer JWT and a service request owned by that customer. Completed runs and their provider
score snapshots are stored in the same MongoDB database as users, providers, service
requests, and interactions.

The Phase 9 integration-readiness endpoint is deliberately fail-closed. Until the real
Component 2 implementation is merged, it reports that Component 4 is ready but the complete
production pipeline is still awaiting Component 2.

Phase 10 validates artifact loading, deterministic sequential/concurrent ranking, candidate
preservation, the Top-5 limit, and conservative in-process latency/throughput thresholds.
Run the versioned operational gate from `packages/backend`:

```powershell
.\.venv\Scripts\python.exe scripts\validate_component4_release.py
```

The release-readiness endpoint exposes this checksum-validated evidence. Passing this gate
means Component 4 is operationally ready; it does not replace a production infrastructure
load test or the real Component 2 integration UAT.

Phase 11 enforces the complete Component 2 handoff lineage at the ranking boundary. The
authenticated customer must match `user_id`; Component 2 and model versions affect the
deterministic run identity and are persisted with both the run and provider snapshots. The
development fixture is rejected whenever `APP_ENV=production`. The handoff-readiness
endpoint reports these controls separately from the still-pending real Component 2
connection.

Phase 12 marks the independently validated Component 4 implementation as a release candidate.
It adds bounded process-local ranking telemetry, an administrator-only runtime-metrics
endpoint, and an authenticated external HTTP/shared-Mongo load-test runner:

```powershell
.\.venv\Scripts\python.exe scripts\load_test_component4_api.py --help
```

The final-readiness endpoint remains fail-closed for whole-pipeline production: the real
Component 2 UAT and a successful load-test report from the deployed shared environment are
still required. See `docs/integration/component4-phase12-release-candidate.md`.

Component 4 loads and validates the Phase 5 provider-score snapshot on its first API request,
then reuses the immutable in-memory index for the process lifetime. It supports newly
registered Component 1 providers by applying the versioned category-prior fallback until
Component 4 review evidence exists. It rejects IDs that exist in neither the validated
snapshot nor the live `providers` collection.

Example request:

```json
{
  "source": "component2",
  "request_id": "RABC123",
  "user_id": "UABC123",
  "component_version": "component2-v1",
  "model_version": "context-filter-v1",
  "provider_ids": [
    "P00001",
    "P00002",
    "P00003",
    "P00004",
    "P00005",
    "P00006",
    "P00007",
    "P00008",
    "P00009",
    "P00010"
  ],
  "top_k": 5,
  "force_recalculate": false
}
```

Repeated identical requests reuse the persisted deterministic run unless
`force_recalculate` is true.

## Test

```powershell
python -m pytest
```

Verify the configured MongoDB connection and required indexes without starting the API:

```powershell
python scripts/verify_database.py
```

Create an administrator account (the password is requested securely and is not echoed):

```powershell
python scripts/seed_admin.py --email admin@example.com --full-name "Platform Admin"
```

Running the same command again refreshes an existing admin account. It will never convert an
existing customer or provider account into an administrator.
