# Component 1 - Hybrid Recommendation Engine

Owner workspace for TF-IDF, multilingual Sentence Transformer, credibility-based collaborative filtering, and hybrid Top-20 retrieval.

Current supplied inputs:

- 10,000 provider records
- 100,000 user interaction records
- 20,000 user request records
- Google Colab training/evaluation notebook

The research notebook exports evaluation CSV and PNG files. The production artifact
exporter recreates the validated notebook pipeline and writes the fitted TF-IDF state,
provider embeddings, credibility state, user preferences, provider lookup data, and a
checksummed manifest for the backend inference service.

From `packages/backend`, after installing `requirements-dev.txt`, run:

```powershell
& .\.venv\Scripts\python.exe ..\..\ml\components\component1\src\export_artifacts.py
```

The generated artifacts are written to
`packages/backend/app/components/component1/artifacts`. Binary model files are tracked
with Git LFS.

## Backend contract

Authenticated customers call `POST /api/v1/component1/recommend` with the canonical
service request ID and query fields. The response preserves both `request_id` and
`user_id`, reports the component/model versions, and returns at most 20 providers with
normalized TF-IDF, BERT, CF, and hybrid scores.

```json
{
  "request_id": "R0123456789AB",
  "query": "Need an electrician for house wiring",
  "category": "Electrician",
  "district": "Colombo",
  "city": "Kottawa",
  "min_rating": 4.0,
  "top_k": 20
}
```

The service validates every tracked artifact checksum, manifest schema, hybrid weights,
row count, embedding shape, provider identifier, and numeric matrix before serving
recommendations. Missing or invalid artifacts never fall back to random providers.
