# weda.lk Frontend

React and TypeScript client for authentication, customer service requests, Component 1
relevance matching, and Component 4 trust-aware final ranking.

```powershell
corepack pnpm install
corepack pnpm --filter @weda/frontend dev
```

The frontend uses `http://localhost:8000/api/v1` by default. Override it with
`VITE_API_BASE_URL` in `packages/frontend/.env` when needed.

## Component 4 Top-5 flow

The customer search page:

1. Creates the authenticated service request.
2. Loads the Component 1 Top-20 relevance candidates.
3. Passes up to ten unique candidate IDs through the previous-stage handoff.
4. Calls `POST /api/v1/component4/rank`.
5. Displays the final five CATF-ranked providers with aspect scores, trust score,
   credibility, evidence sufficiency, and reliability.
6. Allows the customer to save a final provider selection in account history.

Component 2 has not been merged into the active repository. For development only, the
handoff module uses the first ten unique Component 1 IDs and the page labels this clearly as
a `Component 2 integration fixture`. It must not be reported as real Component 2 output.

```env
VITE_COMPONENT2_HANDOFF_MODE=component1-top10-fixture
```

When Component 2 is available, replace the fixture implementation in
`src/component2-handoff.ts` with its returned Top-10 IDs. The Component 4 API client and
Top-5 UI do not need a contract change.

The fixture is development-only. Production builds fail closed and disable recommendation
execution while `VITE_COMPONENT2_HANDOFF_MODE=component1-top10-fixture`. The reserved
`component2-api` mode also remains disabled until the real adapter exists. Phase 9 UAT and
the required inbound contract are documented in
`docs/integration/component4-phase9-uat.md`.

Run frontend validation:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run test
npm.cmd run build
```
