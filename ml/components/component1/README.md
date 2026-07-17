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
