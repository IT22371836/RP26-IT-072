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

## Phase 4 - Review credibility and fake-review detection

Phase 4 fits a `StandardScaler` and Isolation Forest on the Phase 1/2 training split. It
calibrates the fake-review decision threshold on validation labels and reports final metrics
only on the held-out test split. Target columns (`is_fake_review` and `credibility_score`),
identifiers, and split names are explicitly excluded from model features.

Install the lightweight Phase 4 dependencies, or reuse `.venv312` from Phase 3:

```powershell
.\.venv312\Scripts\python.exe -m pip install -r ml\components\component4\requirements-phase4.txt
```

Run a small end-to-end smoke test:

```powershell
.\.venv312\Scripts\python.exe ml\components\component4\src\train_credibility.py --smoke-test --artifact-dir .cache\component4-phase4-smoke\artifacts --report-dir .cache\component4-phase4-smoke\reports
```

Run full Phase 4 training:

```powershell
.\.venv312\Scripts\python.exe ml\components\component4\src\train_credibility.py
```

Versioned outputs:

- `artifacts/credibility-v1/credibility_pipeline.joblib` - scaler, detector, fixed
  validation threshold, and train-only score-normalization bounds.
- `artifacts/credibility-v1/feature_contract.json` - ordered non-leaking input features and
  output semantics.
- `artifacts/credibility-v1/training_config.json` and `manifest.json` - reproducibility,
  immutable input hashes, artifact hashes, and headline test metrics.
- `reports/credibility-v1/credibility_metrics.json` - train/validation/test metrics with the
  test split clearly identified as the headline result.
- `reports/credibility-v1/credibility_confusion_matrix.png`,
  `credibility_score_distribution.png`, and `credibility_threshold_curve.png`.

The full row-level `credibility_predictions.csv` contains all 25,000 review IDs, mapped and
source provider IDs, original targets, and Phase 4 predictions. It is generated locally and
recorded in the manifest, but remains Git-ignored because it is reproducible.

Score a feature CSV with the validated production loader:

```powershell
.\.venv312\Scripts\python.exe ml\components\component4\src\credibility_inference.py --input-csv input_features.csv --output-csv credibility_predictions.csv
```

Phase 4 does not combine ABSA and credibility scores, aggregate provider reviews, implement
CATF Top-10-to-Top-5 ranking, seed MongoDB, or add API/UI integration.

## Phase 5 - Category-Adaptive Trust Fusion and Top-5 ranking

Phase 5 applies the saved Phase 3 ABSA model and Phase 4 credibility pipeline to all 25,000
mapped reviews. For each aspect, signed sentiment is `P(Positive) - P(Negative)` and the
review weight is the maximum class probability multiplied by predicted credibility. Provider
aspect scores are confidence/credibility-weighted means. Category-specific aspect weights
produce a base score, which is normalized to 0..1 and smoothed with the Phase 2 category prior:

```text
effective_reviews = sum(review_credibility)
reliability = effective_reviews / (effective_reviews + 20)
final_CATF = reliability * normalized_base + (1 - reliability) * category_prior
```

Run the complete deterministic build:

```powershell
.\.venv312\Scripts\python.exe -m pip install -r ml\components\component4\requirements-phase5.txt
.\.venv312\Scripts\python.exe ml\components\component4\src\build_catf_scores.py
```

Versioned outputs:

- `artifacts/catf-v1/provider_catf_scores.csv` - all 10,000 Component 1 providers, including
  4,976 with mapped review evidence and 5,024 category-prior fallbacks.
- `artifacts/catf-v1/category_aspect_weights.json` and `catf_config.json` - explicit,
  versioned formulas, category weights, evidence thresholds, and tie-break rules.
- `artifacts/catf-v1/manifest.json` - hashes for all immutable inputs and tracked outputs.
- `reports/catf-v1/catf_audit.json` - preservation, mapping, category, range, and fallback
  validation.
- `reports/catf-v1/demo_top10_to_top5.json` - deterministic contract demonstration using
  real Component 1 provider IDs. Its candidate list is a Phase 5 fixture, not Component 2
  output.
- `reports/catf-v1/provider_score_distribution.png`, `reliability_curve.png`, and
  `demo_top5_ranking.png`.

The row-level `review_fusion_predictions.csv` is reproducibly generated for all 25,000
reviews and remains Git-ignored. It retains review IDs, mapped and source provider IDs,
ratings, split names, ABSA probabilities, signed sentiment, confidence, credibility, and
fusion weights without copying review text.

Filter up to ten Component 2 candidates to at most five Component 4 results:

```powershell
.\.venv312\Scripts\python.exe ml\components\component4\src\catf_ranking.py --request-id REQ-001 --provider-ids P00001 P00002 P00003 P00004 P00005 P00006 P00007 P00008 P00009 P00010
```

The ranker rejects duplicates and unknown IDs, never introduces a provider outside the input
candidate set, and uses `final score DESC`, `effective review count DESC`, `mean credibility
DESC`, then `provider ID ASC`. The run ID is deterministic even if the same candidate IDs are
supplied in a different order.

Category-weight profiles have passed structural validation. Ranking-ground-truth evaluation
(NDCG/Precision@K) remains explicitly pending the planned evaluation phase; Phase 5 does not
claim that validation.

Phase 5 does not write MongoDB data or add backend/frontend endpoints. Live Component 2
candidate integration, shared database persistence, API schemas, and UI wiring begin only in
Phase 6.

## Phase 6 - Shared MongoDB persistence and ranking API

Phase 6 integrates the versioned Phase 5 score snapshot into the active FastAPI backend
without importing TensorFlow, Pandas, or the research pipeline into the web process. The
backend validates artifact byte counts and SHA-256 hashes once, keeps the immutable 10,000
provider score index in memory, and persists ranking runs to the application's configured
shared MongoDB database.

MongoDB collections:

- `component4_runs` - request ownership, candidates, versions, timing, status, and the
  reproducible response snapshot.
- `component4_provider_scores` - one document per returned provider with rank, CATF score,
  aspect scores, credibility/evidence fields, and all active versions.

The normal application index setup creates the required unique and compound indexes for both
collections. No separate Component 4 database or `.env` file is used.

API routes:

- `POST /api/v1/component4/rank`
- `GET /api/v1/component4/runs/{run_id}`
- `GET /api/v1/component4/models`
- `GET /api/v1/component4/weights/{category}`
- `GET /api/v1/component4/health`

`rank` requires a customer JWT, verifies that `request_id` belongs to that customer, accepts
one to ten unique canonical provider IDs, and returns at most five candidates. Unknown IDs
return 404. A registered provider that is available in the shared `providers` collection but
not in the Phase 5 research snapshot receives the versioned category-prior fallback with
explicit insufficient-evidence status.

Component 2 is not implemented in the active repository yet. Therefore, Phase 6 exposes its
strict candidate handoff contract but does not fabricate Component 2 output. Connecting the
previous stage and replacing the current Component 1 Top-20 frontend result with the final
Top-5 display remains the Phase 7 boundary.

## Phase 7 - Previous-stage handoff and frontend Top-5

Phase 7 connects the active React customer search flow to the Phase 6 Component 4 API. The
page renders the returned Top-5 with final CATF score, four aspect summaries, review
credibility, effective review count, reliability, evidence sufficiency, artifact version,
and deterministic run ID. A customer can save a provider from the final list as a `selected`
interaction in the same account history used by the rest of the platform.

The active repository still has no Component 2 implementation. Phase 7 therefore uses a
small, isolated development adapter that takes the first ten unique IDs from Component 1.
The UI identifies this as `Component 2 integration fixture`; it is never labelled or claimed
as actual temporal/contextual filtering. The adapter always supplies at most ten IDs and
Component 4 always returns at most five.

Configuration:

```env
VITE_COMPONENT2_HANDOFF_MODE=component1-top10-fixture
```

The replacement boundary is `packages/frontend/src/component2-handoff.ts`. When Component 2
is merged, that adapter should return Component 2's real Top-10 IDs while the Component 4 API
and Top-5 presentation remain unchanged.

Phase 7 automated tests cover the exact ten-ID request, five-result rendering, fixture
disclosure, aspect/evidence presentation, authenticated API request, and selected-provider
history. Production evaluation and removal of the temporary handoff depend on the real
Component 2 implementation.

## Phase 8 - Held-out proxy ranking evaluation

Phase 8 evaluates the CATF Top-5 ordering without leaking evaluation targets into ranking
evidence. Train and validation review predictions are the only ranking evidence. The test
split is used only to create an independent provider-level proxy relevance target:

```text
review proxy relevance = (rating / 5) * actual credibility score
provider proxy relevance = mean(review proxy relevance over held-out test reviews)
```

This target does not use ABSA predictions, CATF scores, or ranking positions. Providers are
placed into deterministic category-consistent groups of ten using a versioned SHA-256 seed.
The groups are offline evaluation fixtures and are explicitly not Component 2 output. The
last group in each category wraps from the beginning only as needed so all held-out providers
receive one primary assignment while every query still has exactly ten unique candidates.

Run Phase 8 after the Phase 5 review-fusion output has been generated:

```powershell
py -3.12 -m pip install -r ml\components\component4\requirements-phase8.txt
py -3.12 ml\components\component4\src\evaluate_ranking.py
```

Phase 8 compares CATF with average rating, CATF without credibility weighting, and CATF with
uniform aspect weights. It reports `NDCG@5`, `Precision@5`, `Recall@5`, and `MAP@5`, including
per-query and per-category breakdowns:

- `artifacts/evaluation-v1/evaluation_config.json` - frozen split, proxy, fixture, method,
  and metric contracts.
- `artifacts/evaluation-v1/manifest.json` - byte counts and SHA-256 hashes for every input
  and tracked output.
- `reports/evaluation-v1/ranking_evaluation.json` - audit, aggregate metrics, paired CATF
  deltas, and explicit limitations.
- `reports/evaluation-v1/proxy_ground_truth.csv` and `evaluation_queries.csv` - auditable
  proxy providers and deterministic candidate membership.
- `reports/evaluation-v1/query_metrics.csv`, `method_metrics.csv`, and
  `category_metrics.csv`.
- `reports/evaluation-v1/ranking_method_comparison.png` and `category_ndcg_at_5.png`.

The current run uses 21,004 train/validation reviews as ranking evidence and 3,996 held-out
test reviews as the proxy target, with zero split overlap. It covers 2,731 held-out providers
in 278 ten-candidate queries across all 14 categories.

CATF improves over the average-rating baseline on the current held-out proxy. The uniform
weight ablation is marginally higher than category-adaptive weights on some aggregate
metrics, so Phase 8 does not claim that the PDF-guided category weights are empirically
superior. The proxy is not human or production ground truth. Final production validation
still requires real Component 2 candidates and independent relevance judgements.
