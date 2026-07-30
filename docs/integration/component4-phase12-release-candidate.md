# Component 4 Phase 12 Release Candidate

## Outcome

Phase 12 completes the independently deliverable Component 4 implementation. The component is
a validated release candidate with immutable model evidence, deterministic Top-10 to Top-5
ranking, shared-Mongo persistence, authenticated handoff lineage, runtime observability, and a
real HTTP load-test harness.

This is not a whole-pipeline production approval. Component 2 is still external to this branch.

## Final readiness

```text
GET /api/v1/component4/final-readiness
```

The endpoint reports:

- `component4_release_candidate_ready: true`
- `component2_connected: false`
- `external_api_load_test_passed: false`
- `production_ready: false`

The last three values must not be changed without evidence from the deployed shared
environment.

## Runtime telemetry

```text
GET /api/v1/component4/runtime-metrics
Authorization: Bearer <administrator JWT>
```

The endpoint is administrator-only and exposes process-local counters:

- successful, client-error, and server-error ranking requests;
- fresh rankings and cache hits;
- cache-hit ratio;
- average and maximum latency;
- fixed latency buckets;
- process start time and uptime.

The collector is bounded and stores no request IDs, user IDs, provider IDs, tokens, request
bodies, or response bodies. Counters reset when the API process restarts and must be aggregated
outside the process for multi-worker or multi-instance deployment.

## External API and MongoDB load test

The versioned default workload is in:

```text
ml/components/component4/artifacts/acceptance-v1/acceptance_config.json
```

The runner exercises the deployed authenticated HTTP route and its shared-Mongo read/cache
path. Set the JWT in an environment variable so it does not appear in shell history or the
report:

```powershell
$env:COMPONENT4_LOAD_TEST_TOKEN = "<customer-jwt>"
.\.venv\Scripts\python.exe scripts\load_test_component4_api.py `
  --base-url http://localhost:8000/api/v1 `
  --request-id RABC123 `
  --user-id UABC123 `
  --provider-ids P00001 P00002 P00003 P00004 P00005 P00006 P00007 P00008 P00009 P00010 `
  --source component2 `
  --component-version component2-v1 `
  --model-version context-filter-v1 `
  --output ..\..\ml\components\component4\reports\acceptance-v1\api_load_test.json
```

The report never contains the JWT or the supplied request, user, or provider identifiers. The
default acceptance thresholds are:

- 100 measured requests after one warm-up;
- concurrency 10;
- zero contract failures and zero request errors;
- P95 at or below 1000 ms;
- throughput at or above 5 requests per second.

A `development_fixture` run can test infrastructure but cannot satisfy real Component 2 UAT.

## Final production gates

Production readiness can change to true only after all of these are complete:

1. Merge and configure the real Component 2 Top-10 API adapter.
2. Pass the Phase 9 and Phase 11 end-to-end contract/UAT checks with real Component 2 output.
3. Run the Phase 12 load test against the deployed API and shared production-like MongoDB.
4. Review the generated report and confirm every acceptance check passed.

Until then, the release-candidate state is the final honest Component 4 status.
