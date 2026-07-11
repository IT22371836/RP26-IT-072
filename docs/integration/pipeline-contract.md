# Pipeline Contract

This file is the shared integration checkpoint for all four component owners. Field names below are a starting contract and must be updated only through a team-reviewed change.

## Shared identifiers

- `request_id`: unique service request identifier
- `user_id`: customer identifier
- `provider_id`: provider identifier used unchanged across all components and MongoDB
- `category`: normalized service category

## Component hand-offs

### Request to Component 1

`request_id`, `user_id`, `request_text`, `category`, `district`, `city`, `urgency`, and `created_at`.

### Component 1 to Component 2

Top-20 providers with `provider_id`, provider metadata, `tfidf_score`, `bert_score`, `cf_score`, and `hybrid_score`.

### Component 2 to Component 3

Top-10 providers with Component 1 scores plus distance, availability, weather, demand, and `context_score`.

### Component 3 to Component 4

Top-8 providers with prior scores plus verification status, qualification signals, and `credibility_score`.

### Component 4 final output

Top-5 providers with prior scores, aspect sentiment, fraud signals, final score, tier, and human-readable ranking reasons.

## Contract requirements

- Every numeric score passed between components must be normalized to `[0, 1]`.
- Each response must include `component_version` and `model_version`.
- Components must preserve `request_id` and `provider_id` without rewriting them.
- Failure and fallback behavior must be explicit; random provider selection is not an integration fallback.
- API DTOs and persisted MongoDB fields must use the same canonical names.

## Items still requiring team agreement

- Component 2 input data sources and exact context formula
- Component 3 verification fields, model outputs, and tier thresholds
- Component 4 review dataset schema, fraud features, and blending formula
- Ownership of shared provider and request collections
- End-to-end evaluation dataset and success metrics
