# Firebase-only runtime migration

Date: 2026-08-16
Branch: `fn/new-branch4/tharu`
Firebase project: `service-e333a`

## Outcome

FastAPI and the pipeline worker no longer connect to MongoDB. Firebase
Authentication is the identity provider, Firebase Realtime Database is the
runtime database, and Firebase Storage remains the private provider-document
store. FastAPI is retained for Component 1 and Component 4 Python/ML execution.
Component 2 continues to read and write its existing `filter_requests` shape.

## Runtime paths

| Firebase path | Ownership |
|---|---|
| `core/users` | Internal application IDs, roles, and Firebase UID links |
| `core/customer_profiles` | Migrated backend customer profiles |
| `core/provider_verification_events` | Provider verification audit |
| `component1/service_requests` | Service request persistence |
| `component1/interactions` | Impressions, clicks, bookings, completions, ratings |
| `component1/runs` | Component 1 run snapshots |
| `component1/provider_scores` | Ranked Component 1 score snapshots |
| `component4/runs` | Component 4 run responses |
| `component4/provider_scores` | Component 4 CATF score snapshots |
| `pipeline/runs` | Durable 1 → 2 → 4 queue and state machine |
| `pipeline/workers` | Worker heartbeat and active lease |
| `pipeline/idempotency` | Customer/idempotency-key run mapping |
| `providers` | Existing Firebase provider profiles plus missing Mongo fields |

Existing `customers`, `daily_demand`, `filter_requests`, provider reviews, and
research-review nodes were preserved. The two legacy Mongo customer profiles
had no safe Firebase UID/email match, so they remain losslessly available under
`core/customer_profiles`; they were not attached to an unrelated real account.

## Migrated source counts

| Source | Count |
|---|---:|
| Users | 5,009 |
| Backend customer profiles | 2 |
| Providers | 4,999 |
| Service requests | 32 |
| Interactions/bookings/ratings | 569 |
| Component 1 runs / scores | 23 / 460 |
| Component 4 runs / scores | 24 / 141 |
| Pipeline runs / workers | 23 / 1 |

The live Firebase runtime smoke test returned 5,009 internal users, 5,008 total
Firebase providers, 569 interactions, and 32 service requests. The provider
total includes Firebase-only registrations in addition to the migrated source.

## Safety and verification

- The migration was additive. Existing Firebase leaf values were not overwritten.
- Mongo password hashes were excluded; Firebase Authentication owns passwords.
- Preflight found zero value conflicts and zero ambiguous email mappings.
- Post-verification found zero missing leaves across 349,583 compared leaves.
- Eighteen newer Firebase `pipeline/runs/*/execution_log` arrays were preserved
  instead of replacing them with older Mongo snapshots.
- `filter_requests` and `daily_demand` were equal before and after apply.
- Private pre-migration snapshots are stored outside Git at
  `C:\tmp\weda-mongodb-to-firebase-20260816`.
- RTDB rules were compiled and deployed successfully to `service-e333a`.

Machine-readable evidence:

- `mongodb-to-firebase-dry-run.json`
- `mongodb-to-firebase-apply.json`
- `mongodb-to-firebase-post-verify.json`

## Operational note

Do not start MongoDB for the application. Start FastAPI and the one pipeline
worker; both use the Firebase Admin credential configured in the backend `.env`.
Keep the Atlas database and the private backup read-only until a complete normal
pipeline, zero-result fallback, booking, completion, and rating acceptance pass
has been performed. Deleting the Atlas database is a separate destructive step
and was intentionally not performed by this migration.
