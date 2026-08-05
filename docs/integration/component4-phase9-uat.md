# Component 4 Phase 9 Integration and UAT Readiness

## Current decision

The active repository and the latest `fn/dev/nadee` integration branch contain only
Component 2 placeholders. Phase 9 therefore does not fabricate temporal/contextual filtering
or label the Component 1 Top-10 fixture as Component 2 output.

Component 4 is implementation-ready, but the production pipeline is not ready until the real
Component 2 Top-10 implementation is merged.

## Frozen inbound contract

Contract version: `component2-to-component4-v1`.

Component 2 must preserve:

- `request_id`
- `user_id`
- `component_version`
- `model_version`
- between one and ten unique `provider_ids`

Every candidate must be present in the corresponding Component 1 Top-20 response. Component 4
returns at most five providers and never adds a provider outside the supplied candidates.

The frontend contract validator is
`packages/frontend/src/component2-handoff.ts`. The backend readiness endpoint is:

```text
GET /api/v1/component4/integration-readiness
```

Until Component 2 exists, it reports `awaiting_component2`,
`component2_connected: false`, and `production_ready: false`.

## Fail-closed fixture policy

`VITE_COMPONENT2_HANDOFF_MODE=component1-top10-fixture` remains available only in the Vite
development environment. A production build disables recommendation execution when this
fixture is configured. `component2-api` is reserved but also remains fail-closed until its
real API adapter is implemented.

No random, first-N, or category-prior provider list may be presented as Component 2 output in
production.

## UAT gate after Component 2 is merged

1. Replace the development fixture call with the real Component 2 API adapter.
2. Validate request and user identity preservation.
3. Validate one-to-ten unique provider IDs.
4. Validate every Component 2 ID is a subset of the matching Component 1 Top-20.
5. Pass those IDs unchanged to `POST /api/v1/component4/rank`.
6. Validate Component 4 returns at most five candidates and introduces no new IDs.
7. Validate one customer cannot rank or read another customer's request/run.
8. Validate ranking runs and returned provider scores persist in the shared MongoDB.
9. Validate the selected-provider interaction appears in the same customer's history.
10. Run the full backend, frontend, and Component 4 ML regression suites.

Production readiness may change to true only after all ten checks pass using real Component 2
output. The Phase 8 held-out proxy evaluation remains research validation and is not a
substitute for this integration UAT.

## Phase 10 operational evidence

Component 4's independent runtime gate is exposed at:

```text
GET /api/v1/component4/release-readiness
```

This evidence must pass before the post-merge UAT starts. It covers immutable artifact
integrity and in-process sequential/concurrent ranking performance. It does not satisfy steps
1-9 above and does not measure production network or shared MongoDB latency.

## Phase 11 receiving boundary

The strict handoff payload, customer-identity binding, production fixture rejection, upstream
version lineage, and MongoDB audit fields are documented in
[`component4-phase11-handoff.md`](component4-phase11-handoff.md). These controls make the
Component 4 side of the adapter ready, but do not satisfy the real Component 2 steps above.

## Phase 12 release-candidate gate

The final Component 4 operational status, administrator telemetry, and deployed API/shared
MongoDB load-test procedure are documented in
[`component4-phase12-release-candidate.md`](component4-phase12-release-candidate.md). The
external load-test and real Component 2 results must be attached before this UAT can approve
whole-pipeline production readiness.
