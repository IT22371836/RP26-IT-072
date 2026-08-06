# WEB + FastAPI Non-Destructive Integration Checklist

## Goal

Combine the standalone `WEB` React/Firebase application with the existing FastAPI/MongoDB application without deleting, renaming, replacing, or losing any existing database attribute.

Target architecture:

```text
WEB React application
        |
        | HTTPS + JWT
        v
FastAPI API (packages/backend)
        |
        +-- MongoDB: application data and preserved Firebase records
        |
        +-- Component 1 and Component 4 ML services
        |
        +-- Firebase Storage temporarily retained for existing file URLs
```

Firebase RTDB remains read-only during verification and rollback window.

## Verified implementation progress

This section is updated only after the corresponding code and verification pass complete.

Current status as of **2026-08-05**:

- Latest implemented slice: **Phase 6 protected file-storage controls**
- Current backend verification: **120 tests passed; Ruff passed**
- Current WEB verification: **default, hybrid/Firebase-link, and FastAPI builds passed; lint passed with 3 warnings**
- Database safety: **no source migration writes; one isolated MongoDB restore retained for review**
- Pending deployment gate: **deploy the reviewed Storage rules, copy 24 legacy private documents to managed private paths, verify hashes, and revoke anonymously usable legacy download tokens after owner approval**
- Next checklist phase: **Phase 6 external private-document remediation**

| Date | Slice | Result | Evidence |
| --- | --- | --- | --- |
| 2026-08-05 | Immutable Firebase snapshots | Complete | Four `legacy_firebase_*` repositories, unique indexes, SHA-256 comparison, idempotent `$setOnInsert`, conflict reporting |
| 2026-08-05 | Migration CLI foundation | Complete | `--dry-run`, `--apply`, `--verify-only`, `--resume`, dynamic field inventory, JSON reports, non-zero failure status |
| 2026-08-05 | Identity-link foundation | Complete | UID-first and normalized-email matching, explicit matched/ambiguous/unmatched results, immutable `legacy_identity_map` decisions |
| 2026-08-05 | Customer profile extension | Complete | Additive `location` and `customer_image`, WEB camelCase input aliases, partial updates preserve omitted fields |
| 2026-08-05 | WEB FastAPI adapter foundation | Complete | Typed API client, backend-session boundary, customer DTO mapping, Firebase/hybrid/FastAPI data flags, Firebase rollback default |
| 2026-08-05 | WEB React Hooks lint repair | Complete | Conditional administrator-modal Hooks moved before the visibility branch; project lint exits successfully |
| 2026-08-05 | Private provider profile API | Complete | Additive owner PATCH for contact, location, image, language, NIC, and seven-day working hours; public responses exclude private fields |
| 2026-08-05 | WEB provider adapter foundation | Complete | Provider read/update DTOs, seven-day schedule mapping, feature-flagged Firebase/hybrid/FastAPI routing, and Firebase document retention |
| 2026-08-05 | Protected provider documents | Complete | Private list/add/soft-delete/request-verification APIs, Firebase Storage URL retention, atomic locks, WEB feature-flag adapter |
| 2026-08-05 | Administrator provider verification | Complete | Admin-only private review, approve/revoke API, append-only audit events, public privacy boundary, WEB admin adapter |
| 2026-08-05 | Phase 1 migration identity and audit safeguards | Complete | All snapshot/identity indexes verified; duplicate normalized emails produce an explicit ambiguous decision and never select a user |
| 2026-08-05 | Phase 0 technical baseline | Awaiting owner approval | Fresh external backups, SHA-256 hashes, counts/paths/value-shape inventory, exact Firebase emulator restore, 127-document MongoDB restore with matching indexes |
| 2026-08-05 | Phase 2 Firebase attribute preservation | Complete | Fresh 11-record export: 148/148 checklist paths observed, exact immutable snapshot round-trip and hashes, optional/future-field regression coverage |
| 2026-08-05 | Phase 3 additive union model | Complete | UID/email safety rules, unmatched-only public ID allocation, conflict-only additive plans, provider/request preservation, exact request linking, and a zero-write live-state dry run |
| 2026-08-05 | Phase 4 safe backend schema extension | Complete | Optional extra-preserving integration models, allowlisted WEB DTOs, read APIs, optimistic profile concurrency, request ownership checks, and zero replacement-style repository updates |
| 2026-08-05 | Phase 5 authentication transition | Complete | Server-verified one-time Firebase linking, new FastAPI passwords, revocation-aware token verification, role/auth-version binding, production secure-cookie policy, and removal of hard-coded browser administrator credentials |
| 2026-08-05 | Phase 6 protected storage implementation | External remediation required | Backend-controlled private Firebase uploads, owner/admin downloads, dual URLs, SHA-256 metadata/copy verifier, deny-by-default client rules, public DTO/Firebase sanitization, and a zero-write privacy audit |

Latest verification:

- Backend tests: **120 passed**
- Focused migration and union-model tests: **20 passed**
- Focused Phase 4 schema/API safety tests: **10 passed**
- Ruff: **all checks passed**
- Checked-in Firebase dry run: **8 records planned, 5 linkable identities inventoried, 0 failures**
- Live Firebase writes: **none**
- Source MongoDB migration writes: **none; isolated Phase 0 restore only**
- WEB default Firebase build: **passed**
- WEB hybrid/Firebase-link build: **passed**
- WEB lint: **passed with 3 non-blocking warnings and no Hooks-order errors**
- Phase 0 Firebase restore: **11/11 records; exact JSON and canonical hash match**
- Phase 0 MongoDB restore: **127/127 documents; counts and indexes match across 13 collections**
- Phase 2 attribute verification: **11/11 exact snapshots; 148/148 listed paths observed**
- Phase 3 union-model verification: **passed; 8/8 identities safely classified as unmatched, 16 public IDs planned only for those records, 2/2 filter snapshots exact, 2/2 unmatched request links routed to review, 0 source database writes**
- Phase 4 schema-safety verification: **passed; 2/2 filter records and 1/1 daily-demand record round-tripped, all 6 provider integration structures validated, 4/4 required routes present, privacy allowlist passed, 0 repository update violations, 0 source database writes**
- Phase 5 authentication verification: **passed; 5/5 required auth routes present, Firebase Admin 7.5.0 installed, hard-coded administrator credentials and service-account material absent from frontend sources, secure production cookie policy enforced, 1/1 configured backend administrator active, 0 source database writes**
- Phase 6 implementation verification: **passed; 3/3 protected upload/download routes present, public FastAPI and Firebase customer views exclude NIC/documents, dual-URL/hash metadata implemented, the checked-in ruleset denies private client SDK paths, 0 source database writes, 0 storage writes**
- Phase 6 anonymous privacy audit: **failed external gate; all 24 legacy private-document token URLs returned HTTP 200 without authentication. No URL, token, or response body was logged.** Evidence: [`phase6-file-preservation-verification.json`](integration/evidence/phase6-file-preservation-verification.json).

## Non-negotiable preservation rules

- [ ] Never use `$unset`, `replace_one`, collection drops, destructive renames, or overwrite imports during this integration.
- [ ] Never delete Firebase nodes during migration or verification.
- [ ] Treat Firebase keys, Firebase Auth UIDs, MongoDB public IDs, and MongoDB `_id` values as different identifiers.
- [ ] Preserve the original camelCase Firebase attributes exactly as they are.
- [ ] Preserve the existing snake_case MongoDB attributes exactly as they are.
- [ ] Add mapped fields; do not rename or remove source fields.
- [ ] Use only `$setOnInsert` for immutable source snapshots and `$set` for explicitly approved additive fields.
- [ ] Store a raw source snapshot for every migrated record.
- [ ] Make every migration idempotent so rerunning it does not create duplicates.
- [ ] Compare record counts, field-path inventories, and content hashes before any cutover.
- [ ] Keep Firebase available until all acceptance checks and the rollback window are complete.
- [ ] Never migrate passwords. Firebase password hashes and FastAPI password hashes must not be copied between authentication systems.
- [ ] Remove the hard-coded frontend administrator login before production cutover; use backend administrator authorization.

## Current-system inventory

### WEB application

- Location: `WEB`
- Framework: React 19, TypeScript, Vite 8
- Authentication: Firebase Auth
- Database: Firebase Realtime Database
- Files: Firebase Storage
- External data: Open-Meteo and OpenStreetMap/Leaflet
- Database integration file: `WEB/src/config/firebase.ts`
- Seed/export file: `WEB/src/data/service-e333a-default-rtdb-export.json`

### FastAPI application

- Location: `packages/backend`
- API: FastAPI under `/api/v1`
- Authentication: JWT with passwords hashed by the backend
- Database: MongoDB
- Current MongoDB collections:
  - `users`
  - `customer_profiles`
  - `providers`
  - `service_requests`
  - `interactions`
  - `component4_runs`
  - `component4_provider_scores`
  - `provider_verification_events`

### Firebase RTDB nodes found in the WEB export

- `customers`
- `providers`
- `filter_requests`
- `daily_demand`

## Phase 0 — Establish a safe migration baseline

- [x] Create a dedicated branch for the integration.
  Active branch: `integration/web-fastapi-nondestructive`.
- [x] Stop manual database schema edits during the migration window.
  The active policy is recorded in `docs/integration/SCHEMA_FREEZE.md`.
- [x] Record the Firebase project ID and MongoDB database name without committing credentials.
  See `docs/integration/evidence/baseline-context.json`.
- [x] Export a fresh Firebase RTDB JSON backup.
- [x] Create a MongoDB backup with `mongodump`.
- [x] Copy both backups to a location outside the working repository.
  Raw backups are under `C:\tmp\weda-phase0-backups\2026-08-05`.
- [x] Record the SHA-256 hash of each backup.
  See `docs/integration/evidence/baseline-hashes.json`.
- [x] Record the document count for every Firebase node and MongoDB collection.
  See `docs/integration/evidence/baseline-counts.json`.
- [x] Record all unique dotted field paths for every source collection/node.
  See `docs/integration/evidence/baseline-field-paths.json`.
- [x] Record the number of null, missing, empty-string, object, and array values for every field.
  See `docs/integration/evidence/baseline-value-shapes.json`.
- [x] Test restoring both backups into separate disposable databases.
  See `docs/integration/evidence/restore-verification.json` and `rollback-test.md`.
- [ ] Obtain approval of the baseline report before any production migration apply operation.
  Technical verification is complete; explicit baseline owner approval is still required.

Suggested evidence directory, containing no credentials or raw personal data:

```text
docs/integration/evidence/
  baseline-counts.json
  baseline-field-paths.json
  baseline-hashes.json
  migration-run-summary.json
  post-migration-counts.json
  post-migration-field-paths.json
  rollback-test.md
```

## Phase 1 — Add migration identity and audit collections

Implementation status: **complete and verified in code/tests**. The collections and indexes are
created additively by backend startup or `--apply`; no live database migration was run because the
Phase 0 backup/approval gate is still intentionally open.

Create these additive MongoDB collections:

### `legacy_firebase_customers`

One immutable document per Firebase customer. Store the original record without changing its names or values.

```json
{
  "source_system": "firebase_rtdb",
  "source_node": "customers",
  "source_key": "<firebase-key>",
  "source_record": "<complete original Firebase object>",
  "source_sha256": "<stable record hash>",
  "imported_at": "<UTC datetime>",
  "migration_version": "firebase-to-mongo-v1"
}
```

### `legacy_firebase_providers`

Use the same envelope and preserve each complete provider under `source_record`.

### `legacy_firebase_filter_requests`

Use the same envelope and preserve each complete filter request under `source_record`.

### `legacy_firebase_daily_demand`

Use the same envelope and preserve each complete demand snapshot under `source_record`.

### `legacy_identity_map`

```json
{
  "entity_type": "customer | provider | request",
  "firebase_key": "<original RTDB key>",
  "firebase_uid": "<Auth UID when known>",
  "mongo_user_id": "<U... when linked>",
  "mongo_customer_id": "<C... when linked>",
  "mongo_provider_id": "<P... when linked>",
  "mongo_request_id": "<R... when linked>",
  "match_method": "uid | normalized_email | explicit_review | newly_created",
  "match_status": "matched | ambiguous | unmatched",
  "created_at": "<UTC datetime>",
  "updated_at": "<UTC datetime>"
}
```

Checklist:

- [x] Add a unique index on `(source_node, source_key)` to every legacy snapshot collection.
- [x] Add a unique index on `(entity_type, firebase_key)` to `legacy_identity_map`.
- [x] Add sparse indexes for `firebase_uid`, `mongo_user_id`, `mongo_customer_id`, `mongo_provider_id`, and `mongo_request_id`.
- [x] Reject a migration rerun if an existing `source_sha256` differs, and report the conflict for review.
- [x] Do not silently choose between multiple users with the same normalized email.
  Multiple matches are recorded as `ambiguous` with reason `duplicate_normalized_email` and no
  `mongo_user_id`.

## Phase 2 — Preserve the complete Firebase attribute inventory

The migration and later API schemas must retain every field below. Optional fields must remain optional; missing fields must not be converted into fabricated values in the immutable snapshot.

Implementation status: **complete and verified against the fresh Phase 0 export**. All 11 records
round-trip into immutable snapshots with exact source objects and hashes. All 148 checklist paths
are observed; arbitrary optional/future fields are also preserved without fabricating absent fields.
See `docs/integration/evidence/phase2-attribute-verification.json`.

### Customer fields

- [x] `id`
- [x] `fullName`
- [x] `email`
- [x] `role`
- [x] `phone`
- [x] `district`
- [x] `city`
- [x] `location.latitude`
- [x] `location.longitude`
- [x] `customerImage`
- [x] `preferredLanguage`
- [x] `createdAt`
- [x] `createdTimestamp`

### Provider base fields

- [x] `id`
- [x] `uid`
- [x] `fullName`
- [x] `email`
- [x] `role`
- [x] `phone`
- [x] `district`
- [x] `city`
- [x] `location.latitude`
- [x] `location.longitude`
- [x] `providerImage`
- [x] `preferredLanguage`
- [x] `createdAt`
- [x] `createdTimestamp`
- [x] `nic`
- [x] `category`
- [x] `experienceYears`
- [x] `skills[]`
- [x] `description`
- [x] `verified`

### Provider working hours

For every day `Monday` through `Sunday`, preserve:

- [x] `workingHours.<day>.isOpen`
- [x] `workingHours.<day>.start`
- [x] `workingHours.<day>.end`

### Provider documents

- [x] `documents.status`
- [x] `documents.verified`

For each of `identityDocument`, `certification`, `businessRegistration`, `experienceProof`, and `portfolioWork`, preserve every array entry and:

- [x] `documents.<category>[].fileId`
- [x] `documents.<category>[].fileName`
- [x] `documents.<category>[].fileUrl`
- [x] `documents.<category>[].format`
- [x] `documents.<category>[].uploadedAt`

### Provider extracted and credibility fields

- [x] `extractedFeatures.provider_id`
- [x] `extractedFeatures.service_category`
- [x] `extractedFeatures.identity_verified`
- [x] `extractedFeatures.certification_count`
- [x] `extractedFeatures.highest_cert_level`
- [x] `extractedFeatures.cert_issuer_reputation`
- [x] `extractedFeatures.business_registered`
- [x] `extractedFeatures.experience_years`
- [x] `extractedFeatures.experience_reference_count`
- [x] `extractedFeatures.portfolio_quality_score`
- [x] `extractedFeatures.portfolio_count`
- [x] `extractedFeatures.credibility.credibilityScore`
- [x] `extractedFeatures.credibility.credibilityLevel`
- [x] `extractedFeatures.credibility.lastEvaluatedAt`
- [x] Preserve any provider-level `credibility` object if it exists in live Firebase even when it is absent from the checked-in sample.

### Filter request fields

- [x] `request_id`
- [x] `user_id`
- [x] `service_date`
- [x] `service_time.start_time`
- [x] `service_time.end_time`
- [x] `location_type`
- [x] `isNewRequest`
- [x] `results.provider_ids[]`
- [x] `output_results.evaluated_at`
- [x] `output_results.provider_ids[]`
- [x] `output_results.recommendation`
- [x] `output_results.weather_risk`
- [x] `output_results.weather_summary`

For every `output_results.evaluated_providers[]` item, preserve:

- [x] `provider_id`
- [x] `provider_name`
- [x] `provider_location.latitude`
- [x] `provider_location.longitude`
- [x] `distance_km`
- [x] `is_available`
- [x] `location_type`
- [x] `recommendation`
- [x] `request_id`
- [x] `service_day`
- [x] `user_id`
- [x] `weather_risk`
- [x] `working_hours_status`

### Daily-demand fields

- [x] `compile_date`
- [x] `start_date`
- [x] `end_date`
- [x] `target_week`
- [x] `last_updated`

For every `by_category.<category>` object, preserve:

- [x] `service_category`
- [x] `Monday`
- [x] `Tuesday`
- [x] `Wednesday`
- [x] `Thursday`
- [x] `Friday`
- [x] `Saturday`
- [x] `Sunday`
- [x] `total_weekly`
- [x] `avg_daily`
- [x] `demand_level`

For every `summary[]` item, preserve:

- [x] `Service Category`
- [x] `Monday`
- [x] `Tuesday`
- [x] `Wednesday`
- [x] `Thursday`
- [x] `Friday`
- [x] `Saturday`
- [x] `Sunday`
- [x] `Total Weekly Orders`
- [x] `Avg Daily Orders`
- [x] `Weekly Demand Level`

## Phase 3 — Define the additive union model

Do not force Firebase records to match the current minimal FastAPI schemas. Extend the MongoDB documents additively and expose explicit integration schemas.

**Status: complete.** The union model and read-only live-state verification are implemented. No production migration was applied: Phase 0 owner approval remains a required gate. The evidence report is [`phase3-union-model-verification.json`](integration/evidence/phase3-union-model-verification.json).

### Identity mapping rules

- [x] Match by Firebase Auth UID first.
- [x] If UID is unavailable, match by normalized email only when exactly one active MongoDB user has that email.
- [x] Mark unsafe matches as `ambiguous`; never guess. *(Role mismatches, inactive accounts, and duplicate normalized emails all produce explicit ambiguous decisions.)*
- [x] Generate a new MongoDB public ID only for an unmatched record. *(The live dry run planned `U` + `C`/`P` IDs for 8 unmatched records and generated none for matched/ambiguous decisions.)*
- [x] Retain the original `id`, `uid`, Firebase node key, and generated MongoDB public IDs. *(Source identifiers remain under `legacy.*`; generated IDs remain in the identity decision.)*
- [x] Never use an email address as a permanent cross-system primary key.

### Additive customer mapping

| Firebase field | MongoDB canonical/additive field | Rule |
| --- | --- | --- |
| `id` / node key | `legacy.firebase_id` | Preserve exactly |
| Auth UID | `legacy.firebase_uid` | Preserve exactly |
| `fullName` | `users.full_name` | Copy only when creating; do not overwrite a populated conflicting value |
| `email` | `users.email` | Normalize for lookup; retain exact source in snapshot |
| `role` | `users.role` | Validate as customer |
| `phone` | `customer_profiles.phone` | Add when absent; flag conflicts |
| `district` | `customer_profiles.district` | Add when absent; flag conflicts |
| `city` | `customer_profiles.city` | Add when absent; flag conflicts |
| `preferredLanguage` | `customer_profiles.preferred_language` | Add alias, retain original |
| `location` | `customer_profiles.location` | Add complete object |
| `customerImage` | `customer_profiles.customer_image` | Retain URL without moving the file initially |
| `createdAt` | `legacy.firebase_created_at` | Parse into a new field; keep original string |
| `createdTimestamp` | `legacy.firebase_created_timestamp` | Preserve number exactly |

### Additive provider mapping

| Firebase field | MongoDB canonical/additive field | Rule |
| --- | --- | --- |
| `id` / `uid` / node key | `legacy.firebase_id`, `legacy.firebase_uid`, `legacy.firebase_key` | Preserve all identifiers |
| `fullName` | `provider_name` | Add when absent; retain `fullName` in snapshot |
| `email` | linked `users.email` | Link through identity map |
| `phone` | `phone` | Additive provider profile field |
| `location` | `location` | Preserve latitude and longitude |
| `providerImage` | `provider_image` | Keep existing Firebase Storage URL |
| `preferredLanguage` | `preferred_language` | Add alias |
| `nic` | `nic` | Treat as sensitive; never return publicly |
| `experienceYears` | `experience_years` | Copy only after numeric validation |
| `workingHours` | `working_hours` | Preserve all seven days and original strings |
| `documents` | `documents` | Preserve complete object and arrays |
| `extractedFeatures` | `extracted_features` | Preserve complete object; do not replace Component 4 scores |
| `verified` | `verification.verified` | Preserve source and record verification provenance |
| `createdAt` / `createdTimestamp` | `legacy.*` | Preserve both values |

Existing MongoDB provider fields that must also remain unchanged:

- [x] `provider_id`
- [x] `user_id`
- [x] `provider_name`
- [x] `category`
- [x] `district`
- [x] `city`
- [x] `experience_years`
- [x] `skills`
- [x] `description`
- [x] `rating`
- [x] `review_count`
- [x] `booking_success_rate`
- [x] `interaction_count`
- [x] `created_at`
- [x] `updated_at`

### Request mapping

Keep Firebase `filter_requests` as contextual filtering records. Do not flatten them into `service_requests` because they contain additional Component 2-style output.

- [x] Link `filter_requests.request_id` to `service_requests.request_id` through `legacy_identity_map` or an explicit `service_request_id` field. *(The identity-map plan links only an exact, unique `request_id`; current unmatched records remain unlinked.)*
- [x] Preserve the complete filter record in `legacy_firebase_filter_requests`. *(Both live filter snapshots round-trip exactly.)*
- [x] Create an additive `context_filter_results` collection for active reads if required. *(Not required in Phase 3: creation is deferred until an active-read API needs a projection; immutable filter snapshots remain authoritative.)*
- [x] Keep the existing MongoDB `service_requests` fields: `request_text`, `category`, `district`, `city`, `urgency`, `request_id`, `user_id`, and `created_at`.
- [x] Never manufacture missing `request_text`, `category`, `district`, or `city` from unrelated Firebase values. *(The request plan always emits an empty service-request update.)*
- [x] Route ambiguous or incomplete requests to a migration review report. *(Both current filter requests have no service-request match and appear under `review_reasons.no_service_request`.)*

## Phase 4 — Extend backend schemas safely

**Status: complete.** Schema validation and API safety are implemented and verified without applying a production migration. Phase 0 owner approval remains required before any apply operation. Evidence: [`phase4-schema-safety-verification.json`](integration/evidence/phase4-schema-safety-verification.json).

- [x] Add integration Pydantic models for location, working hours, provider documents, extracted features, credibility, context-filter results, and daily demand.
- [x] Make migrated legacy fields optional so old MongoDB documents remain valid. *(Integration models allow missing known fields and preserve unknown future attributes.)*
- [x] Keep API response names stable for existing `packages/frontend` consumers. *(Existing response models were not renamed; the full backend regression suite passes.)*
- [x] Use explicit response DTOs for `WEB`; do not expose internal MongoDB `_id`, password hashes, NIC values, or private document URLs. *(New integration reads are allowlisted; authenticated owner/administrator document-review contracts remain separate.)*
- [x] Add aliases or an adapter for camelCase WEB payloads and snake_case FastAPI payloads. *(Models accept both forms and serialize Firebase-compatible names where WEB requires them.)*
- [x] Add validation tests proving unknown legacy fields are retained in database writes. *(Extra fields survive integration-model round trips, while `$set` profile edits leave unknown stored fields unchanged.)*
- [x] Audit every repository update to ensure it uses `$set` rather than document replacement. *(All repository updates use operators; pre-existing Component 4 `ReplaceOne` and `$unset` operations were removed.)*
- [x] Add optimistic concurrency or `updated_at` checks for profile edits. *(Customer/provider PATCH accepts `expected_updated_at` or `expectedUpdatedAt` and returns `409` for stale versions.)*
- [x] Record `migration_version`, `source_system`, and `last_synced_at` without changing source attributes. *(Phase 3 union plans now add all three metadata fields without mutating source records.)*

Required API gaps for WEB:

- [x] Extend customer profile update to support location and customer image.
- [x] Add provider profile update endpoint.
- [x] Add provider working-hours update endpoint. *(Implemented within the authenticated additive `PATCH /providers/me` contract.)*
- [x] Add provider document list/upload/delete/request-verification endpoints. *(Deletion is soft and preserves metadata.)*
- [x] Add administrator provider verification endpoints with administrator role checks.
- [x] Add daily-demand read endpoint. *(`GET /api/v1/integration/daily-demand/current`; authenticated, Firebase-compatible allowlisted response.)*
- [x] Add context/filter request history endpoints. *(`GET /api/v1/integration/filter-requests`; administrator-only, bounded to 500 records.)*
- [x] Confirm existing Component 1 recommendation endpoints meet WEB search requirements. *(The endpoint preserves its Top-20 contract and now rejects missing or foreign service-request IDs.)*
- [x] Confirm existing Component 4 ranking endpoints receive authenticated customer IDs and valid request IDs. *(Existing checks bind both `user_id` and the persisted request owner to the authenticated customer.)*

## Phase 5 — Authentication transition

Recommended approach: FastAPI JWT becomes the application authorization source while Firebase Auth is temporarily used only to verify and link existing identities.

**Status: complete.** The implementation is complete without changing or deleting any legacy database attribute. Production deployment still needs `FIREBASE_PROJECT_ID`, server-only Application Default Credentials, secure HTTPS origins, and an authenticated browser E2E run. Evidence: [`phase5-auth-transition-verification.json`](integration/evidence/phase5-auth-transition-verification.json).

- [x] Remove the hard-coded administrator email/password logic from the frontend. *(The synthetic administrator login and credential display were removed; a static regression test scans both frontend source trees.)*
- [x] Seed a backend administrator using `packages/backend/scripts/seed_admin.py`. *(The configured database contains one explicitly active backend administrator record. The idempotent seed script securely prompts for a password and refuses to convert customer/provider accounts.)*
- [x] Add a one-time account-link flow for existing Firebase users. *(`POST /api/v1/auth/link/firebase` accepts a verified Firebase ID token and rejects an already-linked UID.)*
- [x] Verify the Firebase ID token server-side before linking a Firebase UID. *(Firebase Admin verifies token signature, project audience, expiry, email verification, and optionally revocation; revocation checking defaults to enabled.)*
- [x] Require the user to establish a new FastAPI password or use a secure password-reset flow. *(The one-time link requires a new password; authenticated users can rotate it with `POST /api/v1/auth/password`, which invalidates older tokens.)*
- [x] Never send Firebase admin credentials or service-account keys to the browser. *(Frontend configuration contains only Firebase client settings; Admin SDK credentials are loaded on the backend through server-only Application Default Credentials.)*
- [x] Store JWT access tokens according to the project security decision; prefer secure, HTTP-only cookies for production. *(Production settings fail closed unless cookie transport and `Secure` are enabled; `HttpOnly` and configurable `SameSite` are applied. Bearer transport remains available for local development.)*
- [x] Enforce customer/provider/administrator roles in FastAPI, not in React. *(Every protected request reloads the user and binds JWT role plus `auth_version` to current database state.)*
- [x] Test disabled users, expired tokens, wrong roles, duplicate emails, and ambiguous identity links. *(Nine focused Phase 5 tests cover these cases, one-time linking, cookie-only authentication/logout, password rotation, and frontend secret scanning; the current full 120-test backend suite passes.)*

## Phase 6 — File and document preservation

The easiest non-destructive option is to retain existing Firebase Storage objects and URLs during the database migration.

**Status: implementation complete; external remediation required.** New private uploads use backend-controlled Firebase Storage objects with non-public `gs://` locations, server-computed SHA-256 metadata, and owner/administrator-only content routes. The checked-in legacy values remain unchanged. The anonymous audit proved that 24/24 legacy private token URLs are currently readable without authentication, so Phase 6 cannot be marked fully complete until an approved copy/hash/token-revocation operation is performed. Evidence: [`phase6-file-preservation-verification.json`](integration/evidence/phase6-file-preservation-verification.json).

- [x] Keep every existing `fileUrl`, `providerImage`, and `customerImage` value unchanged.
- [x] Do not delete or move Firebase Storage objects during database cutover.
- [x] Add backend metadata and authorization around new uploads.
- [x] Decide whether new uploads continue to use Firebase Storage or move to a backend-controlled object store. *(Firebase Storage is retained, but new private provider documents are uploaded by FastAPI/Firebase Admin and served only through role-checked backend routes. Public profile images retain their existing transition behavior.)*
- [x] If files are later copied, store both `legacy_url` and `current_url`. *(Both additive fields are supported without replacing `file_url`; new managed objects also record `storage_path`, content type, and size.)*
- [x] Verify hashes after copying each file. *(New uploads receive a server-computed SHA-256, downloads verify it, and the copy-manifest verifier rejects mismatched source/current files. No legacy copy has been authorized or performed yet.)*
- [ ] Confirm private identity and certification documents are not publicly readable. *(Blocked: an anonymous HEAD audit returned HTTP 200 for all 24 legacy identity/certification/business/experience URLs. Required remediation: copy to managed private paths, verify hashes, retain both URLs, then revoke legacy download tokens after owner approval.)*
- [x] Never return `nic` or identity-document URLs in a public provider response. *(FastAPI `ProviderPublic` excludes both; the Firebase customer adapter now strips `nic` and the complete `documents` object, and the customer NIC renderer was removed.)*

## Phase 7 — Build the idempotent migration command

Add a versioned backend script, for example:

```text
packages/backend/scripts/migrate_firebase_rtdb_v1.py
```

Required modes:

- [x] `--input <firebase-export.json>`
- [x] `--dry-run`
- [x] `--apply`
- [x] `--resume`
- [x] `--report <output.json>`
- [x] `--verify-only`

Required behavior:

- [x] Validate the JSON before connecting to MongoDB.
- [x] Reject inputs whose top-level structure is unexpected.
- [x] Inventory every source field path dynamically; do not rely only on the checked-in sample.
- [x] Write immutable legacy snapshots first.
- [x] Build identity mappings second.
- [ ] Add canonical fields third.
- [ ] Process records in bounded batches.
- [ ] Use transactions where supported or maintain a resumable migration journal.
- [ ] Log record IDs and status, but do not log passwords, tokens, NICs, or document content. *(Conflict/failure IDs are reported; per-record success journaling begins in the next slice.)*
- [ ] Produce counts for imported, matched, created, unchanged, ambiguous, invalid, and failed records. *(Snapshot counts are implemented; identity-match counts begin in the next slice.)*
- [x] Exit non-zero when any field is lost, any count is unexplained, or any record fails.

Example execution sequence after the script exists:

```powershell
Set-Location packages\backend
.\.venv\Scripts\Activate.ps1

python scripts\migrate_firebase_rtdb_v1.py `
  --input ..\..\WEB\src\data\service-e333a-default-rtdb-export.json `
  --dry-run `
  --report ..\..\docs\integration\evidence\migration-dry-run.json

python scripts\migrate_firebase_rtdb_v1.py `
  --input ..\..\WEB\src\data\service-e333a-default-rtdb-export.json `
  --apply `
  --report ..\..\docs\integration\evidence\migration-run-summary.json

python scripts\migrate_firebase_rtdb_v1.py `
  --input ..\..\WEB\src\data\service-e333a-default-rtdb-export.json `
  --verify-only `
  --report ..\..\docs\integration\evidence\post-migration-verification.json
```

Do not run `--apply` against production until the dry run and disposable-database restore have passed review.

## Phase 8 — Introduce a WEB API adapter

Do not rewrite every component at once. Add an adapter boundary:

```text
WEB/src/config/api.ts
WEB/src/config/auth-store.ts
WEB/src/services/customer-service.ts
WEB/src/services/provider-service.ts
WEB/src/services/request-service.ts
WEB/src/services/demand-service.ts
```

- [x] Add `VITE_API_BASE_URL=http://localhost:8000/api/v1` to `WEB/.env.example`.
- [ ] Never commit real Firebase or backend secrets. *(The new `.env.example` contains placeholders only; removal of legacy hard-coded Firebase defaults and administrator credentials remains pending.)*
- [x] Create one typed API client for JSON requests and authorization headers.
- [ ] Convert camelCase UI models to snake_case API DTOs only at the adapter boundary.
- [ ] Convert API DTOs back to existing WEB view models without removing attributes.
- [ ] Preserve unmapped data under an `extensions` or `legacy` property in frontend models when needed.
- [ ] Replace direct Firebase calls feature by feature.
- [x] Keep `firebase.ts` available behind an explicit feature flag during migration.
- [ ] Do not silently fall back to browser `localStorage` in production.
- [x] Display a real error when backend writes fail.

Suggested feature flags:

```env
VITE_DATA_SOURCE=hybrid
VITE_AUTH_SOURCE=firebase-link
VITE_FILE_STORAGE_SOURCE=firebase
```

Allowed transition values:

```text
VITE_DATA_SOURCE: firebase | hybrid | fastapi
VITE_AUTH_SOURCE: firebase | firebase-link | fastapi
VITE_FILE_STORAGE_SOURCE: firebase | backend
```

## Phase 9 — Migrate WEB features one at a time

For every feature below, complete unit tests, API contract tests, and browser tests before moving to the next feature.

### 9.1 Authentication

- [ ] Customer registration through FastAPI.
- [ ] Provider registration through FastAPI.
- [ ] Login and logout through FastAPI.
- [ ] Current-user restoration through `/auth/me`.
- [ ] Administrator role controlled by FastAPI.

### 9.2 Customer profile

- [ ] Read the FastAPI profile. *(Adapter and linked-session path are implemented and build-verified; authenticated browser E2E remains pending.)*
- [ ] Update phone, district, city, preferred language, location, and image. *(Adapter and backend contract tests pass; authenticated browser E2E remains pending.)*
- [x] Confirm all original Firebase customer fields remain in the immutable snapshot.

### 9.3 Provider profile

- [ ] Read and update provider base profile. *(Backend and WEB adapter are implemented; authenticated browser E2E remains pending.)*
- [ ] Read and update working hours. *(Backend and seven-day WEB mapping are implemented; authenticated browser E2E remains pending.)*
- [ ] Upload and manage documents. *(Backend and WEB adapter are implemented with Firebase Storage retention and soft deletion; authenticated browser E2E remains pending.)*
- [ ] Request verification. *(Backend and WEB adapter are implemented with locking; authenticated browser E2E remains pending.)*
- [ ] Administrator verification. *(Backend, audit trail, role tests, and WEB adapter are implemented; authenticated browser E2E remains pending.)*
- [ ] Display credibility and extracted features.
- [ ] Confirm existing MongoDB ML fields are unchanged.

### 9.4 Service and filter requests

- [ ] Create a FastAPI service request.
- [ ] Run Component 1 recommendations.
- [ ] Preserve or integrate the contextual filter result.
- [ ] Send the valid Top-10 handoff to Component 4.
- [ ] Display Component 4 Top-5 results.
- [ ] Persist interactions, selections, completion, cancellation, rating, and review.

### 9.5 Demand, maps, and weather

- [ ] Read daily-demand data through FastAPI.
- [ ] Preserve every category and summary field.
- [ ] Keep Leaflet/OpenStreetMap in the frontend.
- [ ] Keep Open-Meteo in the frontend initially or proxy it through FastAPI later.

## Phase 10 — Dual-read and controlled-write verification

- [ ] Start with Firebase reads and shadow MongoDB reads.
- [ ] Compare normalized results without changing either source.
- [ ] Report all field, type, array-order, and record-count differences.
- [ ] Switch one feature to MongoDB reads after it reaches 100% explained parity.
- [ ] During any temporary dual-write period, assign one writer as authoritative per entity.
- [ ] Add idempotency keys to create operations.
- [ ] Prevent update loops by storing `source_system` and `sync_version`.
- [ ] Never use last-write-wins when the two sources contain different non-empty values; create a conflict record.
- [ ] Monitor error rates and reconciliation differences during the rollback window.

## Phase 11 — Tests and acceptance gates

### Preservation tests

- [ ] Source record count equals imported snapshot count for every Firebase node.
- [ ] Every source key exists exactly once in a legacy collection.
- [ ] Every source record hash matches the imported `source_record` hash.
- [ ] Every unique source field path exists in the imported snapshots.
- [ ] Arrays preserve their item count, item values, and order.
- [ ] Null, missing, false, zero, and empty-string values remain distinguishable.
- [ ] All existing MongoDB fields remain present and unchanged unless an approved user action updates them.
- [ ] No MongoDB collection contains duplicate public IDs.
- [ ] Every matched record has an identity-map entry.
- [ ] Every ambiguous record appears in the migration report.

### Backend tests

- [x] Run `python -m pytest` from `packages/backend`.
- [ ] Add tests for camelCase/snake_case adapters.
- [ ] Add tests for extra legacy-field persistence.
- [x] Add tests for role authorization and private fields.
- [ ] Add tests for migration reruns and interrupted-resume behavior.
- [ ] Add tests proving update operations do not replace whole documents.
- [ ] Run `python scripts/verify_database.py`.

### WEB tests

- [x] Run `npm.cmd run build` from `WEB`.
- [x] Run `npm.cmd run lint` and fix the conditional React Hook errors before production cutover.
- [ ] Test customer, provider, and administrator flows.
- [ ] Test maps, working hours, document lists, verification state, demand data, and weather.
- [ ] Test empty, incomplete, legacy-only, and newly created profiles.
- [ ] Test expired sessions and backend unavailability.

### Security tests

- [ ] No administrator password exists in frontend source or the JavaScript bundle.
- [ ] No service-account credential exists in the repository or browser bundle.
- [x] NIC is not exposed by public provider APIs.
- [x] Identity documents are not exposed by public APIs.
- [ ] Firebase Storage rules and MongoDB access are least-privilege.
- [ ] CORS permits only the deployed WEB origins.
- [ ] Production uses a non-development JWT secret and HTTPS.

## Phase 12 — Cutover and rollback

### Cutover

- [ ] Announce and begin a short write-free migration window if live Firebase data can change.
- [ ] Take final Firebase and MongoDB backups.
- [ ] Run the final incremental migration.
- [ ] Run `--verify-only` and all acceptance gates.
- [ ] Set `VITE_DATA_SOURCE=fastapi`.
- [ ] Set `VITE_AUTH_SOURCE=fastapi` after account linking is complete.
- [ ] Keep `VITE_FILE_STORAGE_SOURCE=firebase` until a separate verified file migration is complete.
- [ ] Deploy FastAPI, then deploy WEB.
- [ ] Monitor API errors, authentication failures, record conflicts, and ML handoff failures.

### Rollback

- [ ] Keep the previous WEB build deployable.
- [ ] Restore the frontend flags to Firebase/hybrid mode if acceptance metrics fail.
- [ ] Stop new FastAPI writes before restoring MongoDB.
- [ ] Restore only from the tested backup; do not attempt ad hoc reverse transformations.
- [ ] Reconcile records written after cutover before reopening writes.
- [ ] Record the rollback reason and affected identifiers without logging sensitive values.

## Definition of done

The integration is complete only when every item below is true:

- [ ] WEB uses FastAPI for authentication, profiles, service requests, interactions, recommendations, ranking, and administrative authorization.
- [ ] All Firebase RTDB records are preserved byte-for-byte logically in immutable MongoDB snapshot documents.
- [ ] All Firebase field paths listed in this document—and any additional paths discovered from the live export—are preserved.
- [ ] All pre-existing MongoDB attributes remain present.
- [ ] Identity mapping has no unexplained duplicate, missing, or ambiguous production record.
- [ ] Component 1 and Component 4 operate through authenticated FastAPI requests from WEB.
- [ ] Existing Firebase file URLs remain valid or have hash-verified replacements while retaining the legacy URLs.
- [ ] Backend, frontend, migration, reconciliation, and security tests pass.
- [x] Production lint has no React Hooks errors.
- [ ] No frontend administrator password or backend secret is shipped to the browser.
- [ ] Backups and rollback have been successfully tested.
- [ ] Evidence reports are reviewed and approved.
- [ ] Firebase RTDB is changed to read-only only after the rollback window; deletion is a separate future decision and is not part of this plan.

## Recommended first implementation slice

Complete this smallest vertical slice before attempting the full migration:

- [x] Implement the immutable snapshot collections and dry-run migration report.
- [ ] Import and verify customers only in a disposable MongoDB database.
- [x] Implement identity linking for one test customer.
- [x] Add location and image fields to the backend customer profile additively.
- [x] Add the WEB API adapter.
- [ ] Move one test customer's profile read/update flow to FastAPI.
- [ ] Verify that the Firebase record, legacy MongoDB snapshot, and canonical MongoDB profile all retain their complete attributes.
- [x] Demonstrate rollback to Firebase mode using only environment flags.

After this slice passes, repeat the same pattern for providers, documents, filter requests, daily demand, and the ML pipeline.
