# Integration schema freeze

Status: active from 2026-08-05 until the migration acceptance checks and rollback window close.

Scope:

- Firebase project: `service-e333a`
- MongoDB database: `Weda_platform_renew_dev`
- Integration branch: `integration/web-fastapi-nondestructive`

Rules:

- Do not make manual schema, index, collection, Firebase node, or security-rule edits.
- Do not delete, rename, replace, or overwrite source fields or records.
- Apply additive changes only through reviewed repository code or versioned migration scripts.
- Record every approved exception with the reason, owner, timestamp, affected paths, and rollback steps.
- Regenerate the Phase 0 baseline and backups after any approved exception before continuing migration work.

The source Firebase RTDB remains read-only for migration activity. The isolated MongoDB restore
database `weda_p0_restore_20260805` is verification-only and must never be used by the application.

