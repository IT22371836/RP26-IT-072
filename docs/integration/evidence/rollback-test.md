# Phase 0 backup restore verification

Date: 2026-08-05

## Backup location

Raw backups are stored outside the repository at:

`C:\tmp\weda-phase0-backups\2026-08-05`

The repository evidence contains hashes, counts, paths, and value-shape statistics only. It does
not contain credentials or raw personal records.

## Firebase RTDB

- Source backup: `firebase-rtdb-export.json`
- Restore target: local Firebase RTDB emulator v4.11.2, namespace `demo-weda-phase0`
- Result: passed
- Exact JSON comparison: passed
- Record counts: 11 expected, 11 restored
- Source database writes: none
- Emulator state: stopped after verification

## MongoDB

- Backup method: MongoDB Database Tools v100.17.0 `mongodump --archive --gzip`
- Source database: `Weda_platform_renew_dev`
- Restore target: isolated database `weda_p0_restore_20260805`
- Restore method: `mongorestore --archive --gzip` with namespace remapping
- Result: passed
- Document counts: 127 expected, 127 restored
- Collection count and index comparisons: passed for all 13 collections
- Source database writes: none
- Restore database state: retained temporarily for approval/review; it is not application-configured

Machine-readable details are in `restore-verification.json`.

## Approval

Technical verification is complete. Baseline owner approval remains pending and must be recorded
before any production migration apply operation.

