# Component 4 Phase 11 Handoff Lineage

## Scope

Phase 11 hardens the receiving boundary between Component 2 and Component 4. It does not
claim that Component 2 is connected. It ensures that a future real Component 2 Top-10 result
can be authenticated, validated, ranked, and audited without losing its source identity.

The active contract remains `component2-to-component4-v1`.

## Ranking request

`POST /api/v1/component4/rank` requires a customer JWT and the complete handoff:

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

Required lineage fields:

- `source`: `component2` or `development_fixture`
- `request_id`: unchanged shared service-request ID
- `user_id`: unchanged customer ID
- `component_version`: upstream component implementation version
- `model_version`: upstream context-filter model version
- `provider_ids`: one to ten unique canonical provider IDs

## Enforced controls

- The authenticated customer must equal the handoff `user_id`.
- The service request must exist and belong to the same customer.
- Provider IDs are normalized, deduplicated by rejection, and limited to ten.
- A `component2` handoff cannot use the `not-component2` placeholder versions.
- A `development_fixture` handoff is forbidden when `APP_ENV=production`.
- Source and upstream versions are part of the deterministic Component 4 run ID.
- The response preserves the handoff lineage.
- MongoDB run and ranked-provider snapshots preserve the same lineage.
- Component 4 still returns at most five providers and never adds a non-candidate provider.

## Readiness endpoint

```text
GET /api/v1/component4/handoff-readiness
```

The endpoint reports `contract_enforced`, `identity_binding_enforced`,
`lineage_persistence_enabled`, and `fixture_blocked_in_production` as independent Component 4
controls. It intentionally reports:

```text
component2_connected: false
production_ready: false
```

Those values may change only after the real Component 2 adapter and the post-merge UAT pass.

## Post-merge verification

After Component 2 is available:

1. Configure the frontend `component2-api` adapter.
2. Capture a real Component 1 Top-20 and Component 2 Top-10 for the same request.
3. Prove that every Top-10 ID is contained in the matching Top-20.
4. Submit the unchanged Component 2 handoff to Component 4.
5. Confirm the response and MongoDB snapshots preserve the exact source versions.
6. Confirm changing only the upstream model version creates a different auditable run ID.
7. Complete the Phase 9 end-to-end UAT and shared-Mongo infrastructure load test.
