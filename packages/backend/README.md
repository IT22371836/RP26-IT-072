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
- `POST /api/v1/auth/link/firebase`
- `POST /api/v1/auth/password`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/providers/me`
- `GET /api/v1/providers/me`
- `PATCH /api/v1/providers/me`
- `GET /api/v1/providers/me/documents`
- `POST /api/v1/providers/me/documents/{category}`
- `DELETE /api/v1/providers/me/documents/{category}/{file_id}` (soft delete)
- `POST /api/v1/providers/me/request-document-verification`
- `GET /api/v1/providers/{provider_id}`
- `GET /api/v1/admin/providers` (administrator; includes private review metadata)
- `PATCH /api/v1/admin/providers/{provider_id}/verification`
- `GET /api/v1/admin/providers/{provider_id}/verification-events`
- `POST /api/v1/service-requests`
- `GET /api/v1/service-requests/me`
- `GET /api/v1/service-requests/{request_id}`
- `POST /api/v1/component1/recommend` (customer; requires an owned service request)
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
- `GET /api/v1/integration/daily-demand/current` (authenticated)
- `GET /api/v1/integration/filter-requests` (administrator only)

Customer and provider profile updates accept an optional `expected_updated_at` (or
`expectedUpdatedAt`) value. When supplied, a stale edit returns `409 Conflict` instead of
overwriting a newer profile version. Existing clients may omit it during the transition.

The integration read endpoints use explicit allowlisted response models. MongoDB `_id`,
password hashes, NIC values, arbitrary legacy extras, and private document URLs are not
serialized by these endpoints. The immutable `legacy_firebase_*` snapshots remain the full
source of truth for every original and future Firebase attribute.

## Phase 5 authentication transition

FastAPI is the authorization source. During the transition, an existing customer or
provider signs in to Firebase once and sends the resulting Firebase ID token together with
a newly chosen FastAPI password to `POST /api/v1/auth/link/firebase`. The backend verifies
the token with Firebase Admin, requires a verified email, rejects ambiguous normalized-email
matches, and stores the Firebase UID additively. Administrator accounts cannot use this link
flow and must be provisioned with `scripts/seed_admin.py`.

Local development uses bearer tokens by default. Production configuration fails closed
unless secure cookie transport and Firebase server verification are configured:

```dotenv
APP_ENV=production
AUTH_COOKIE_ENABLED=true
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_STORAGE_BUCKET=your-firebase-project-id.firebasestorage.app
FIREBASE_CHECK_REVOKED=true
```

Provide Firebase Admin credentials only to the backend through Application Default
Credentials, for example by setting `GOOGLE_APPLICATION_CREDENTIALS` in the server runtime.
Never place a service-account JSON file or private key in a `VITE_*` variable or browser
bundle. Login, account linking, and password rotation return the JWT only as an `HttpOnly`,
`Secure`, `SameSite` cookie when production cookie transport is enabled. Password rotation
increments `auth_version`, so previously issued tokens stop authorizing requests.

Verify the Phase 5 controls and configured administrator record without database writes:

```powershell
python scripts/verify_phase5_auth_transition.py `
  --check-mongodb `
  --report ..\..\docs\integration\evidence\phase5-auth-transition-verification.json
```

## Phase 6 private file preservation

Firebase Storage remains the object store during the transition. New private provider
documents are uploaded through FastAPI/Firebase Admin to `private/providers/...`; the API
stores a non-public `gs://` current URL, SHA-256, content type, size, and storage path. It
does not create a Firebase download token. Providers and administrators retrieve content
through separate role-checked endpoints with hash verification and `private, no-store`
responses:

- `POST /api/v1/providers/me/documents/{category}/upload`
- `GET /api/v1/providers/me/documents/{category}/{file_id}/content`
- `GET /api/v1/admin/providers/{provider_id}/documents/{category}/{file_id}/content`

Set `FIREBASE_STORAGE_BUCKET` on the backend and use
`VITE_FILE_STORAGE_SOURCE=backend` for the protected rollout. `WEB/storage.rules` denies
browser SDK access to private document paths. Public profile-image paths remain readable
during the rollback window.

Verify code controls, preserved URL inventory, future copy manifests, and anonymous legacy
access without modifying either database or storage:

```powershell
python scripts/verify_phase6_file_preservation.py `
  --input ..\..\WEB\src\data\service-e333a-default-rtdb-export.json `
  --anonymous-audit `
  --report ..\..\docs\integration\evidence\phase6-file-preservation-verification.json
```

The current audit reports that all 24 legacy private download-token URLs are anonymously
readable. Their values and objects were left unchanged. Copying, hash-verifying, and revoking
those legacy tokens remains an owner-approved production operation; it must also preserve
both `legacy_url` and `current_url` metadata.

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

## Non-destructive Firebase RTDB migration

Inventory the checked-in WEB Firebase export without connecting to MongoDB:

```powershell
python scripts/migrate_firebase_rtdb_v1.py `
  --input ..\..\WEB\src\data\service-e333a-default-rtdb-export.json `
  --dry-run
```

The versioned migration stores exact, immutable source records in dedicated
`legacy_firebase_*` collections. It never replaces an existing snapshot. A rerun with the
same source is reported as unchanged, while changed source content is reported as a conflict.
Review the full [non-destructive integration checklist](../../docs/WEB_FASTAPI_NON_DESTRUCTIVE_INTEGRATION_CHECKLIST.md)
before using `--apply` or `--verify-only` against a configured MongoDB database.

Verify the Phase 4 schemas, response privacy boundary, required routes, and repository update
operators against an export without writing to either database:

```powershell
python scripts/verify_phase4_schema_safety.py `
  --input ..\..\WEB\src\data\service-e333a-default-rtdb-export.json `
  --report ..\..\docs\integration\evidence\phase4-schema-safety-verification.json
```

### Customer booking-history migration

New booking lifecycle state is stored canonically at
`customers/{firebase_uid}/bookingHistory/{booking_id}` in Firebase RTDB. Component 1 reads
that history for personalization; Mongo `interactions` booking events are retained only as a
temporary compatibility shadow while the remaining Mongo-to-Firebase migration is completed.
Customer browser sessions cannot mutate `bookingHistory`; trusted Firebase Admin operations
create bookings and apply provider completion/cancellation and customer rating transitions.

Preview the Mongo booking-history backfill without writing to Firebase:

```powershell
python scripts/migrate_booking_history_to_firebase.py --dry-run
```

After reviewing the counts, apply and independently verify it:

```powershell
python scripts/migrate_booking_history_to_firebase.py --apply `
  --report ..\..\docs\integration\evidence\booking-history-apply.json
python scripts/migrate_booking_history_to_firebase.py --verify-only `
  --report ..\..\docs\integration\evidence\booking-history-verify.json
```

The configured Firebase Admin credential must be available for `--apply` and `--verify-only`.
Reruns are idempotent for matching booking identities; conflicting Firebase records stop the
migration instead of being replaced.

Create an administrator account (the password is requested securely and is not echoed):

```powershell
python scripts/seed_admin.py --email admin@example.com --full-name "Platform Admin"
```

Running the same command again refreshes an existing admin account. It will never convert an
existing customer or provider account into an administrator.
