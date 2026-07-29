# weda.lk Frontend

React and TypeScript client for authentication, customer service requests, and the
Component 1 Top-20 provider recommendation workflow.

```powershell
corepack pnpm install
corepack pnpm --filter @weda/frontend dev
```

The frontend uses `http://localhost:8000/api/v1` by default. Override it with
`VITE_API_BASE_URL` in `packages/frontend/.env` when needed.
