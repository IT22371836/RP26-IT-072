# Project Architecture

This repository separates deployable application code from research and model-training work.

## Top-level layout

```text
.
|-- packages/                 Deployable applications
|   |-- frontend/             React + TypeScript web client
|   `-- backend/              FastAPI + MongoDB API and ML inference
|-- ml/                       Research-only training work
|   `-- components/
|       |-- component1/       Hybrid recommendation engine
|       |-- component2/       Temporal and contextual matching
|       |-- component3/       Skill verification and credibility
|       `-- component4/       Review intelligence and fraud detection
|-- docs/
|   |-- integration/          Cross-component API and data contracts
|   `-- reference/            Research guides supplied by the team
|-- infrastructure/           Deployment and local infrastructure definitions
`-- old/                      Legacy implementation; never imported at runtime
```

## Component workflow

Each member develops training code under `ml/components/componentN`. Only stable inference code and exported artifacts are integrated into `packages/backend/app/components/componentN`.

```text
raw data -> notebook/training code -> evaluation -> exported artifact
                                                    |
                                                    v
                                          backend inference service
                                                    |
                                                    v
                                          shared pipeline contract
```

## Frontend boundaries

- `src/app`: application bootstrap, providers, and routing.
- `src/features`: user-facing feature modules.
- `src/shared`: UI, API client, hooks, types, and utilities shared by features.
- Feature code must not import another feature's internal files.
- Cross-component request and response types belong in `src/shared/types`.

## Backend boundaries

- `app/api`: HTTP routing only.
- `app/core`: configuration, MongoDB connection, logging, and security.
- `app/components`: independent inference modules for Components 1-4.
- `app/pipeline`: orchestration across Components 1-4.
- `app/repositories`: MongoDB persistence operations.
- `app/schemas`: shared Pydantic request and response contracts.
- `app/services`: application use cases that are not owned by one ML component.

Routes call services or component interfaces, never model implementations directly. A component must expose a typed service interface so that another team member can replace its internal model without changing the full pipeline.

## Data and model rules

- Treat `data/raw` files as immutable source material.
- Write cleaning outputs to `data/processed`; do not overwrite raw inputs.
- Store evaluation tables and plots in `reports`.
- Store deployable model files in `artifacts` with a manifest describing version, training data, metrics, and required runtime.
- Never commit credentials or personal data. Local secrets belong in `.env` only.
- `old/` is reference material and must not be imported by new code.

## Integration flow

1. Component 1 retrieves the Top-20 relevant providers.
2. Component 2 applies availability and contextual constraints and returns Top-10.
3. Component 3 verifies qualifications and returns Top-8 with credibility signals.
4. Component 4 applies review intelligence and fraud-aware blending to return the final Top-5.

The exact payload fields must be agreed in `docs/integration/pipeline-contract.md` before component APIs are implemented.
