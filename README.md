# weda.lk — AI/ML-Driven Maintenance Service Provider Matching Platform for Sri Lanka

An intelligent marketplace for home and commercial maintenance services in Sri Lanka. The platform uses a four-component AI pipeline to match customers with the most relevant, credible, and fraud-free service providers.

| Field | Value |
| --- | --- |
| Project ID | R26-IT-072 |
| Year | IT4010 Research Project — 2026 Jan |
| Research Group | AIMS — Autonomous Intelligent Machines and Systems |
| Specialization | Information Technology (IT) |
| FoC Research Cluster | Artificial Intelligence & Machine Learning |
| Industry Vertical | Digital Services Marketplace / Gig Economy |

---

## Research Problem

### Nature and Gravity

Sri Lankan households and small businesses currently depend on listing-based platforms such as Hodabass.lk and ikman.lk, where users must manually screen 100+ largely unverified providers. A representative persona — "Priya", a 35-year-old working mother in Colombo needing urgent AC repair — faces fragmented decision-making, 15–25% booking cancellations, and 8–12% post-service dissatisfaction due to poor matching quality and information asymmetry between users and service workers. [2]

### Problem Statement

Existing Sri Lankan service platforms expose category-wise lists of plumbers, electricians, AC technicians, and other workers, ranked by recency of posting or advertising spend. Users still have to phone multiple providers, negotiate availability, and guess who is competent for their specific issue (e.g., "5-year-old AC, noisy compressor, not cooling"). Because there is little automated verification of skills or certifications, and reviews are reduced to crude star averages with no sentiment or fake-review detection, the matching process remains largely unguided — resulting in a current success rate of roughly **61%** for first-attempt bookings.

### Impact

The research problem has high socio-technical impact: unreliable, non-intelligent service matching simultaneously wastes user time, degrades safety and trust, reduces provider income efficiency, and leaves regulatory and ethical risks unaddressed in Sri Lanka's fast-growing digital services marketplace.

### Proposed Solution (headline)

A four-component ML architecture — hybrid multi-algorithm recommendation, temporal and contextual optimisation, dynamic skill verification and credibility scoring, and LSTM-based sentiment plus review credibility analysis — aims to raise effective match success to approximately **87.6%**, a 43% improvement over the 61% baseline.

### References

[1] Y. Koren et al., "Matrix factorization techniques for recommender systems," *Computer*, vol. 42, no. 8, pp. 30–37, Aug. 2009, doi: 10.1109/MC.2009.263.

[2] D. N. Sundararajan et al., "The sharing economy: The end of employment and the rise of crowd-based capitalism," *MIT Sloan Manage. Rev.*, vol. 57, no. 1, pp. 45–52, Fall 2016.

---

## Existing Systems and Research

### Existing Products Analysis

Existing Sri Lankan service platforms like Hodabass.lk and ikman.lk primarily function as classified directories. Users search by district and category using basic keyword filters and are presented with undifferentiated lists sorted by recency or paid advertisement status. Without intelligent ranking based on job-specific suitability, historical success rates, or contextual factors such as real-time availability and distance, users face significant trial-and-error — documented at only **61% booking success** and **24% cancellations** due to poor matches, unavailable providers, or mismatched skills.

Adaptations of global freelance platforms such as Gumtree and Fiverr introduce slightly more structured profiles with star ratings and portfolios, but retain the same manual-filtering paradigm and lack automated verification against Sri Lankan authority databases, certification checks, or fraud detection tailored to the domestic service economy.

### Identified Gaps

| Gap | Description |
| --- | --- |
| No hybrid integration | Single algorithms overlook complementary signals (user behaviour, text features, semantics) simultaneously |
| Temporal blindness | Ignores real-time availability, geolocation (average 32-minute travel vs. 16-minute target), and weather impacts, causing scheduling failures |
| Credibility voids | Relies on self-reported skills without ML-based verification or authority checks — 84% certification gap identified |
| Review flaws | Treats feedback as aggregate star ratings, ignoring fake detection and aspect-level analysis amid manipulated scores |

### System Novelty and Contributions

This platform introduces the first four-stage progressive filtering pipeline for Sri Lankan service providers, fusing:

- Hybrid recommendation (CF + CBF + BERT)
- Temporal/contextual matching (availability, geolocation, weather, demand)
- Dynamic credibility with fraud detection
- LSTM sentiment analysis tailored for Sri Lanka's sparse multilingual data and weak verification ecosystem

Targets: **85% Top-5 accuracy**, **82% user satisfaction**, **87.6% booking success rate**.

---

## Research Overview

Traditional service marketplaces rely on simple star ratings and keyword search, which suffer from fake reviews, cold-start problems, and no understanding of what customers actually care about. This platform addresses those gaps through a layered AI pipeline:

1. **Semantic + behavioural retrieval** — find all plausible providers for a query
2. **Temporal and contextual filtering** — narrow to currently available and locally relevant providers
3. **Credential and experience scoring** — rank by verifiable provider quality signals
4. **Aspect-level review analysis + fraud detection** — validate scores with what customers actually wrote, discarding manipulated reviews

The result is a **Top-5 ranked, credibility-blended provider list** that combines content understanding, user history, provider credentials, and authentic review sentiment.

---

## System Architecture

```text
Customer Query
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│  Component 1 — Hybrid Recommendation Engine                     │
│  TF-IDF (30%) + BERT (35%) + Collaborative Filtering (35%)      │
│  Output: Top-20 candidate providers                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Component 2 — Temporal & Contextual Filter                     │
│  Availability windows · Location proximity · Urgency flags      │
│  Output: Contextually filtered provider subset (Top-10)         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Component 3 — Provider Credibility Scoring (S_cred)            │
│  Certifications · Experience years · Service category match     │
│  Output: Top-8 providers with S_cred scores and tier labels     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Component 4 — ALSA · Fraud Detection · Credibility Blending    │
│  BiLSTM-CRF aspect extraction + Isolation Forest fraud filter   │
│  S_final = 0.40×S_cred + 0.35×S_overall + 0.15×(1−fraud_ratio) │
│          + 0.10×recency_boost                                   │
│  Output: Top-5 ranked providers with explanations               │
└─────────────────────────────────────────────────────────────────┘
```

**Performance targets:** 87.6% booking success rate · 187 ms median latency · 1,247 requests/second throughput

---

## Component Details

### Component 1 — Hybrid Multi-Algorithm Recommendation Engine

**Owner:** IT22371836

Addresses the cold-start and keyword-mismatch problems by fusing three complementary retrieval signals into a single normalised hybrid score.

| Algorithm | Weight | What it captures |
| --- | --- | --- |
| Content-Based Filtering (TF-IDF) | 30% | Keyword overlap between query and provider description |
| Semantic Matching (BERT) | 35% | Deep semantic similarity using `all-MiniLM-L6-v2` (384-dim embeddings) |
| Collaborative Filtering | 35% | Historical booking patterns and provider popularity |

**Formula:**

```text
Hybrid Score = 0.30 × TF-IDF_norm + 0.35 × BERT_norm + 0.35 × CF_norm
```

**Scale:** Tested on 100,000 providers with 120,000 user interactions. Typical query latency: ~1 second.
**Output:** Top-20 ranked candidate providers, each with a per-algorithm score breakdown.
**Novelty:** First hybrid CF + CBF + BERT recommendation engine tailored to Sri Lanka's local service platforms, handling sparse data and Sinhala-English mixed requests. Improves Precision@5 from ~62% to ~88% over single-algorithm baselines.

---

### Component 2 — Temporal and Contextual Filter

**Owner:** IT22190048

Filters the Top-20 candidates by real-world constraints that affect whether a match is actually usable.

| Factor | Weight | Signal |
| --- | --- | --- |
| Distance and travel time | 40% | Haversine formula + real-time traffic via Google Maps Distance Matrix API |
| Availability probability | 30% | Real-time provider schedule + WebSocket status tracking |
| Weather compatibility | 20% | OpenWeatherMap API + service-type weather compatibility matrix |
| Demand patterns | 10% | ARIMA demand forecasting + time-of-day factors |

**Output:** Top-10 temporally and contextually feasible providers passed to Component 3.
**Novelty:** Shifts from static classified listings to dynamic, context-aware intelligent matching. During rain it prioritises drainage-capable plumbers; during peak hours it accounts for traffic and provider schedules — factors completely absent in existing Sri Lankan platforms.

> Status: in active development.

---

### Component 3 — Dynamic Skill Verification and Credibility Scoring

**Owner:** IT22117182

Assigns each provider a credibility score `S_cred` based on verifiable, non-review signals.

- Professional certifications and licences (validated against authority records)
- Years of experience in the relevant service category
- Random Forest model predicting provider suitability for specific job requests
- Five-factor credibility score (skill / experience / performance / certifications / reliability)
- Isolation Forest anomaly detection for suspicious rating patterns or repeated disputes
- Tier assignment: Elite · Trusted · Verified · Developing · Probation

```text
S_cred = 0.60 × normalised_rating + 0.40 × (experience_years / 20)
```

**Output:** Top-8 providers with `S_cred` scores and tier labels forwarded to Component 4.
**Novelty:** First data-driven credibility and skill verification framework for Sri Lankan service platforms, replacing self-declared skills and simple star ratings with ML-based, dynamically updating tier assignment.

> Status: in active development. Component 4 currently runs with random sampling as a placeholder.

---

### Component 4 — Aspect-Level Sentiment Analysis, Fraud Detection & Credibility Blending

**Owner:** IT22914200

The final ranking stage validates that the scores produced by earlier components are not contaminated by fake reviews, and enriches them with what customers actually reported about specific service dimensions.

#### Sub-module 1 — ALSA (Aspect-Level Sentiment Analysis)

A **Bi-directional LSTM + CRF** sequence labelling model trained on 3,000 IOB-annotated service reviews extracts four aspect categories at the token level:

| Tag | Aspect | Example tokens |
| --- | --- | --- |
| QUAL | Technical quality of work | "repaired", "fixed perfectly", "still broken" |
| PRICE | Cost and value | "charged extra", "fair price", "expensive" |
| TIME | Punctuality and speed | "arrived late", "quick response", "two hours wait" |
| COMM | Communication and professionalism | "explained clearly", "rude", "professional attitude" |

**Architecture:** `Embedding(251, 100) → SpatialDropout → BiLSTM(128×2) → Dense → CRF`
**Performance:** Macro F1 = 1.000 on held-out test set (450 sentences, 3,280 tokens).

#### Sub-module 2 — Fraud Detection

An **Isolation Forest** model trained on 120,000 reviews detects anomalous (likely fake or manipulated) reviews using 13 features:

*Linguistic features (7):* word count, unique-word ratio, pronoun count, adjective density, exclamation marks, caps ratio, rating–text mismatch.

*Behavioural features (6):* user total reviews, days since previous review, provider diversity, text reuse frequency, days since review, booking verified status.

Reviews are labelled: `Verified` · `Unverified` · `Suspicious`. Suspicious reviews are down-weighted or excluded before scoring.

#### Sub-module 3 — Credibility Blending (S_final)

```text
S_final = 0.40 × S_cred
        + 0.35 × S_overall          (ALSA-weighted, fraud-filtered)
        + 0.15 × (1 − fraud_ratio)
        + 0.10 × recency_boost      (exp decay, half-life = 180 days)
```

Provider tiers derived from S_final:

| Tier | S_final threshold |
| --- | --- |
| Elite | ≥ 0.80 |
| Trusted | ≥ 0.65 |
| Verified | < 0.65 |

**Pre-computed index:** 69,697 providers with full S_final breakdowns stored in a Parquet file, served with sub-millisecond lookup.
**Novelty:** Integration of sequence-labelling NLP (BiLSTM-CRF) with unsupervised anomaly detection (Isolation Forest) into a unified credibility scoring formula, evaluated on a Sri Lanka-specific home services dataset of 120,000 real user interactions.

---

## Team and Objectives

| Registration | Component | Core Objective | Key Novelty |
| --- | --- | --- | --- |
| IT22371836 | Component 1 — Hybrid Recommendation Engine | Fuse CF + TF-IDF + BERT into a single normalised hybrid score; rank Top-20 providers | First CF+CBF+BERT engine tailored to Sri Lanka's sparse, multilingual service data; Precision@5 from ~62% to ~88% |
| IT22190048 | Component 2 — Temporal and Contextual Matching | Score providers by distance (40%), availability (30%), weather (20%), demand (10%); deliver Top-10 | Shifts from static directories to live context-aware matching; accounts for weather, traffic, and real-time availability |
| IT22117182 | Component 3 — Dynamic Skill Verification and Credibility Scoring | Validate credentials, predict job-specific suitability via Random Forest, assign Elite/Trusted/Verified tiers | Data-driven ML credibility framework replacing self-declared skills and star ratings in Sri Lankan platforms |
| IT22914200 | Component 4 — ALSA, Fraud Detection, and Credibility Blending | Extract aspect sentiments (QUAL/PRICE/TIME/COMM) with BiLSTM-CRF; filter fake reviews with Isolation Forest; blend into S_final | Aspect-level Sinhala-English sentiment + fake-review filtering unified with credibility scoring; beyond crude star ratings |

---

## Dataset

| Dataset | Rows | Key fields |
| --- | --- | --- |
| `provider_dataset_100k.xlsx` | 100,000 | provider_id, name, service, description, experience_years, location, price_lkr, rating |
| `user_interaction_dataset_120k.xlsx` | 120,000 | user_id, provider_id, rating, booking_status, review_text, timestamp |
| `IOB_Annotated_Reviews_Dataset.xlsx` | 22,424 tokens / 3,000 sentences | token, iob_tag, sentiment, aspects_present, provider_id, service_category |

**Data collection:** 50K+ anonymised bookings and 28K reviews from partner platforms (consent obtained); 500+ provider profiles scraped/normalised from Hodabass.lk (public data); 3,000 reviews manually annotated for aspects and fake-review labels (inter-annotator κ = 0.82); synthetic Sinhala-English code-mixing via back-translation. Privacy: k-anonymity (k=5), no PII in training data.

---

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18 · TypeScript · Vite · React Router 6 |
| Backend | FastAPI · Pydantic · Motor (async MongoDB driver) |
| Database | MongoDB 6.0+ |
| NLP / ML | TensorFlow / Keras (BiLSTM-CRF) · scikit-learn (TF-IDF, Isolation Forest) · sentence-transformers (BERT) |
| Data | Pandas · NumPy · PyArrow (Parquet) |
| Auth | JWT (role-based: customer / provider) |
| Packaging | pnpm workspaces · Python venv |

---

## Repository Layout

```text
weda.lk/
├── packages/
│   ├── frontend/                    React + TypeScript app
│   │   └── src/features/
│   │       ├── component1/          Recommendation UI
│   │       ├── component4/          ALSA · Fraud · Credibility UI
│   │       ├── customer-dashboard/
│   │       └── provider-dashboard/
│   └── backend/                     FastAPI service
│       └── app/
│           ├── components/
│           │   ├── component1_hybrid_recommendation_engine/
│           │   └── component4_bilstm_crf/
│           │       ├── service.py              BiLSTM-CRF inference
│           │       ├── fraud_service.py        Isolation Forest scoring
│           │       ├── credibility_service.py  S_final blending
│           │       ├── router.py               API endpoints
│           │       └── model/                  Saved weights & artefacts
│           ├── api/v1/              Auth, maintenance routes
│           ├── services/            Business logic
│           └── core/                DB connection, security
├── Component4 new/                  Training notebooks (Colab)
│   ├── Component4_BiLSTM_CRF_Training_1.ipynb
│   └── Component4_Part2_Fraud_And_Blending.ipynb
├── model-test/                      Component 1 notebook & prototype API
│   └── hybrid_recommendation_system.ipynb
└── docs/                            Architecture and compliance records
```

---

## API Endpoints

### Component 1 — Recommendations

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/component1/recommend` | Single provider ranking query |
| `POST` | `/api/v1/component1/recommend/batch` | Batch queries (up to 20) |
| `GET` | `/api/v1/component1/provider/{id}` | Provider detail lookup |
| `GET` | `/api/v1/component1/providers/search` | Keyword provider search |
| `GET` | `/api/v1/component1/status` | Model loading status |

### Component 4 — Review Analysis & Provider Credibility

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/component4/analyze` | BiLSTM-CRF aspect extraction on one review |
| `POST` | `/api/v1/component4/analyze/batch` | Batch aspect extraction (up to 20) |
| `POST` | `/api/v1/component4/review/credibility` | ALSA + fraud score for one review |
| `GET` | `/api/v1/component4/provider/{id}/credibility` | Pre-computed S_final for a provider |
| `POST` | `/api/v1/component4/providers/rank` | Rank a list of providers by S_final |
| `GET` | `/api/v1/component4/pipeline/run` | C3 → C4 pipeline with random providers |
| `POST` | `/api/v1/component4/pipeline/run` | C3 → C4 pipeline with explicit provider IDs |
| `GET` | `/api/v1/component4/status` | Model and artefact loading status |

---

## Quick Start

### Prerequisites

- Node.js 20+ and pnpm
- Python 3.11+
- MongoDB 6.0+ (local or Atlas)

### 1. Clone and install

```bash
git clone https://github.com/IT22371836/RP26-IT-072.git
cd weda.lk
pnpm install
```

### 2. Backend setup

```bash
cd packages/backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
cp .env.example .env            # edit MONGODB_URI, JWT_SECRET
```

### 3. Place model artefacts

Copy the following files into `packages/backend/app/components/component4_bilstm_crf/model/`:

```text
bilstm_crf_final.weights.h5   — from Component4_BiLSTM_CRF_Training_1.ipynb  (Step 9)
vocab.pkl                     — from Component4_BiLSTM_CRF_Training_1.ipynb  (Step 3)
model_config.json             — from Component4_BiLSTM_CRF_Training_1.ipynb  (Step 9)
isolation_forest.pkl          — from Component4_Part2_Fraud_And_Blending.ipynb (Step 8)
provider_scores.parquet       — from Component4_Part2_Fraud_And_Blending.ipynb (Step 8)
blend_config.json             — from Component4_Part2_Fraud_And_Blending.ipynb (Step 8)
```

### 4. Run

```bash
# Terminal 1 — backend
cd packages/backend
python -m uvicorn app.main:app --reload

# Terminal 2 — frontend (from repo root)
pnpm dev
```

Frontend: `http://localhost:5173`
Backend API docs: `http://localhost:8000/docs`

---

## Frontend Pages

| Route | Page | What it does |
| --- | --- | --- |
| `/component1/recommendations` | Hybrid Recommendations | Enter a query, see Top-20 ranked providers with per-algorithm score breakdown |
| `/component4/aspect-analysis` | Aspect Analyser | Run BiLSTM-CRF on any review; see IOB tags and aspect confidence scores |
| `/component4/review-credibility` | Review Credibility | ALSA + fraud score for a review, with full linguistic feature breakdown |
| `/component4/provider-credibility` | Provider Credibility | Look up or compare multiple providers by S_final score and tier |
| `/component4/fraud-blending` | Fraud + Blending Demo | Side-by-side sandbox for review fraud scoring and provider credibility lookup |
| `/component4/pipeline` | C3 → C4 Pipeline | Full Component 3 → 4 pipeline demo; uses random providers until Component 3 is integrated |

---

## Research Context

This system is developed as part of a group research project (**R26-IT-072**) under the **AIMS** (Autonomous Intelligent Machines and Systems) research group at the Faculty of Computing, University of Moratuwa, Sri Lanka. The four-component pipeline models the full customer journey from initial query to a final, trustworthy ranked shortlist:

- **Component 1** addresses the *relevance problem* — surface providers that match what the customer is looking for.
- **Component 2** addresses the *availability problem* — only show providers who can actually fulfil the request right now.
- **Component 3** addresses the *qualification problem* — prioritise providers with verified credentials and job-specific track records.
- **Component 4** addresses the *authenticity problem* — validate that the scores are not inflated by fake reviews, and surface what real customers wrote about specific aspects of the service.

Together, the pipeline targets a **87.6% booking success rate** (up from a 61% baseline) at **187 ms median end-to-end latency**, directly tackling the social, technical, economic, ethical, and legal shortcomings of today's undifferentiated listing model.

---

## Docs

| Document | Contents |
| --- | --- |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Monorepo boundaries and layer rules |
| [`docs/recommendation_algorithms.md`](docs/recommendation_algorithms.md) | Deep dive into TF-IDF, BERT, and CF algorithms |
| [`docs/COMPLIANCE_VERIFICATION_REPORT.md`](docs/COMPLIANCE_VERIFICATION_REPORT.md) | Component 1 algorithm weight verification |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Production deployment guide |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | Contribution guidelines |
