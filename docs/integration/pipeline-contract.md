# Pipeline Contract

This file is the shared integration checkpoint for all four component owners. Field names below are a starting contract and must be updated only through a team-reviewed change.

## Shared identifiers

- `request_id`: unique service request identifier
- `user_id`: customer identifier
- `provider_id`: provider identifier used unchanged across all components and MongoDB
- `category`: normalized service category

The canonical MongoDB collection fields and ownership rules are defined in [`core-data-contract.md`](core-data-contract.md).

## Component hand-offs

### Request to Component 1

`request_id`, `user_id`, `request_text`, `category`, `district`, `city`, `urgency`, and `created_at`.

### Component 1 to Component 2

`request_id`, `user_id`, `component_version`, `model_version`, and exactly Top-20 providers (when at least 20 match the supplied filters) with `provider_id`, provider metadata, `tfidf_score`, `bert_score`, `cf_score`, and `hybrid_score`. The pipeline request fixes `top_k` at `20`.

### Component 2 to Component 4

Component 2 filters the Component 1 Top-20 to at most ten unique providers. The minimum
handoff required by Component 4 is `request_id`, `user_id`, `component_version`,
`model_version`, and `provider_ids`. Component 2 may preserve its contextual features and
scores in its own response, but it must not rewrite provider IDs or introduce a provider
outside the Component 1 candidate set.

### Component 4 final output

At most five providers selected only from the Component 2 candidates, with aspect sentiment,
review credibility, evidence reliability, final CATF score, and version metadata.

## Contract requirements

- Every numeric score passed between components must be normalized to `[0, 1]`.
- Each response must include `component_version` and `model_version`.
- Components must preserve `request_id` and `provider_id` without rewriting them.
- Component 2 candidate IDs must be unique, contain between one and ten items, and remain a
  subset of the corresponding Component 1 Top-20.
- Component 4 must return no more than five items and must never add a non-candidate provider.
- Failure and fallback behavior must be explicit; random provider selection is not an integration fallback.
- The Component 1 Top-10 development fixture is forbidden in production.
- API DTOs and persisted MongoDB fields must use the same canonical names.

## Items still requiring team agreement

- Component 2 input data sources and exact context formula
- Component 2 production endpoint and final response DTO
- Ownership of shared provider and request collections
- End-to-end evaluation dataset and success metrics
