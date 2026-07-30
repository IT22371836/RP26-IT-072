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

## Phase 3 - Multi-task aspect sentiment model

Phase 3 trains one review-level model with four output heads: quality, punctuality,
communication, and professionalism. The encoder is a bidirectional LSTM followed by a real
multi-head self-attention layer. Each head returns probabilities in the frozen
`Positive, Neutral, Negative` order required by the later trust-score calculation.

Create the isolated Python 3.12 training environment from the repository root:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r ml\components\component4\requirements-phase3.txt
```

Run a small end-to-end smoke test first:

```powershell
.\.venv312\Scripts\python.exe ml\components\component4\src\train_absa.py --smoke-test --artifact-dir .cache\component4-phase3-smoke\artifacts --report-dir .cache\component4-phase3-smoke\reports
```

Run full training:

```powershell
.\.venv312\Scripts\python.exe ml\components\component4\src\train_absa.py
```

The saved `.keras` model accepts raw review strings because the train-only adapted
`TextVectorization` layer is embedded in the artifact. Phase 3 exports:

- `artifacts/absa-v1/absa_model.keras` - reloadable multi-output model.
- `artifacts/absa-v1/manifest.json` - versions, immutable input hashes, artifact hashes,
  architecture, and metric summary.
- `artifacts/absa-v1/label_mapping.json` - fixed label and output-head contracts.
- `artifacts/absa-v1/text_vectorization_vocabulary.json` - frozen train vocabulary.
- `artifacts/absa-v1/training_config.json` - reproducibility and class-weight settings.
- `reports/absa-v1/absa_metrics.json` - per-aspect and aggregate test metrics.
- `reports/absa-v1/absa_training_history.csv` - epoch history.
- `reports/absa-v1/absa_training_curves.png` and `absa_confusion_matrices.png`.
- `reports/absa-v1/absa_model_summary.txt` - auditable model structure.

The full row-level `absa_test_predictions.csv` is generated locally and recorded in the model
manifest, but remains Git-ignored because it repeats review text and is reproducible.

Run inference from raw text:

```powershell
.\.venv312\Scripts\python.exe ml\components\component4\src\absa_inference.py --text "The provider arrived on time and communicated clearly."
```

Run Phase 3 tests:

```powershell
.\.venv312\Scripts\python.exe -m pytest ml\components\component4\tests\test_absa_training.py -q
```

Phase 3 reads the Phase 2 mapped reviews and Phase 1 labels without modifying them. It does
not implement provider-level aggregation, CATF ranking, MongoDB persistence, or API/UI
integration.
