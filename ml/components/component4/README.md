# Component 4 - Trust-Aware Review Intelligence

Component 4 is the final ranking layer. Its active contract is Component 2 Top-10 candidate
provider IDs to Component 4 final Top-5 providers. The legacy `old/` implementation and the
repository `main` branch are not implementation sources.

## Phase 1 - Data readiness

Phase 1 freezes the supplied research data and creates reproducible, leakage-safe processed
copies. It does not map Component 4 provider IDs to Component 1 provider IDs; that mapping is
the explicit Phase 2 boundary.

Raw inputs are immutable after freezing:

- `data/raw/customer_reviews_25k.csv`
- `data/raw/aspect_sentiment_labels_25k.csv`
- `data/raw/review_credibility_25k.csv`
- `data/raw/provider_review_summary_5k.csv`
- `notebooks/component4_pp2_full_notebook_with_visualizations.ipynb`

Run Phase 1 from the repository root:

```powershell
packages\backend\.venv\Scripts\python.exe ml\components\component4\src\prepare_data.py
```

The command validates schemas and cross-file keys, then creates:

- Four clean CSV files under `data/processed/`.
- `data/raw/manifest.json` with immutable source hashes and schemas.
- `data/processed/manifest.json` with transformation rules and output hashes.
- `reports/phase1_audit.json` with before/after quality metrics.

Phase 1 transformations are deliberately auditable:

- The original booking ID is retained as `source_booking_id`; a deterministic unique
  `booking_id` is generated from `review_id`.
- The original service type is retained as `source_service_type`; active category names are
  normalized to the Component 1 vocabulary.
- The original split is retained as `source_dataset_split`.
- A SHA-256 group ID is created from Unicode-normalized, case-folded review text.
- The active 70/15/15 split is deterministically assigned by text-group hash, preventing the
  same normalized text from crossing train, validation, and test sets.
- Original review text and labels are not rewritten.

Generated processed CSV files are intentionally ignored by Git because they are reproducible
from the frozen raw files. Their manifest and audit report remain tracked.

## Phase boundary

Do not begin provider-ID mapping, MongoDB seeding, model training, CATF implementation, or API
integration until Phase 1 verification has passed and Phase 2 has been explicitly approved.

## Phase 2 - Deterministic provider mapping

Phase 2 maps every Component 4 research provider to a real Component 1 research-provider ID
without modifying either source dataset. Mapping is a category-scoped, sorted one-to-one
bijection. Given the same frozen inputs, every source provider always receives the same target
provider ID.

Run Phase 2 after Phase 1:

```powershell
packages\backend\.venv\Scripts\python.exe ml\components\component4\src\map_providers.py
```

Tracked Phase 2 contracts and reports:

- `data/processed/provider_id_map.csv` - frozen source-to-target mapping.
- `data/processed/category_priors.json` - category-prior fallback configuration.
- `data/processed/phase2_manifest.json` - input/output hashes and algorithm version.
- `reports/phase2_mapping_audit.json` - mapping, preservation, and fallback validation.

Reproducible generated files (Git-ignored):

- `data/processed/customer_reviews_mapped.csv`
- `data/processed/provider_review_summary_mapped.csv`
- `data/processed/provider_no_review_fallbacks.csv`

Mapped review and provider-summary rows retain the original Component 4 provider ID as
`source_provider_id`. Only the processed `provider_id` value is replaced; review text, labels,
ratings, credibility features, review counts, and original source files remain unchanged.

The fallback configuration uses the empirical mean `trust_sentiment_score` of reviewed source
providers in each category. Any Component 1 provider without mapped reviews receives its
category prior, zero effective reviews, zero reliability, and `insufficient` evidence status.

Phase 2 does not seed MongoDB, train models, implement CATF, or change Component 1 artifacts.
