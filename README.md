# AI/ML Driven Maintenance Service Provider Platform (Sri Lanka)

Monorepo with React (TypeScript) frontend, FastAPI backend, and MongoDB 6.0+.

## Quick Start

1. Install pnpm and Node.js 20+.
2. Install Python 3.11+.
3. Copy env files:
   - `packages/backend/.env.example` to `packages/backend/.env`
4. Install dependencies:
   - `pnpm install`
   - create/activate a Python virtual environment
   - `pip install -r packages/backend/requirements-dev.txt`
5. Run apps:
   - Frontend: `pnpm dev` (from repo root)
   - Backend: `cd packages/backend` then `uvicorn app.main:app --reload --port 8000`
   - Backend (from repo root): `uvicorn app.main:app --reload --port 8000 --app-dir packages/backend --env-file packages/backend/.env`
## Repository Layout

- `packages/frontend`: React app with reusable shared components.
- `packages/backend`: FastAPI service with layered architecture.
- `docs`: Architecture and collaboration guidelines.
