# Component 1 - Hybrid Multi-Algorithm Recommendation Engine

This module wraps the hybrid recommender from the training notebook into a FastAPI-ready service.

## Location
- Training assets are expected under `training/`.
- Saved artifacts are expected under `artifacts/` (created by the notebook).
- You can override the training path with `COMPONENT1_TRAINING_DIR`.
- You can override the artifacts path with `COMPONENT1_ARTIFACTS_DIR`.

## Expected files
- `provider_dataset_100k.xlsx`
- `user_interaction_dataset_120k.xlsx`
- `models/` (optional cache for SentenceTransformer)

## Optional artifacts
- `tfidf_vectorizer.joblib`
- `tfidf_matrix.joblib`
- `provider_embeddings.npy`
- `provider_df.pkl`
- `provider_credibility.pkl`
- `user_preferences.joblib`
- `weights.json`
- `bert_model/`

## Environment overrides
- `COMPONENT1_TRAINING_DIR`
- `COMPONENT1_ARTIFACTS_DIR`
- `COMPONENT1_PROVIDER_DATASET`
- `COMPONENT1_INTERACTION_DATASET`
- `COMPONENT1_EMBEDDINGS_CACHE`
- `COMPONENT1_TFIDF_VECTORIZER`
- `COMPONENT1_TFIDF_MATRIX`
- `COMPONENT1_PROVIDER_ARTIFACT`
- `COMPONENT1_PROVIDER_CREDIBILITY`
- `COMPONENT1_USER_PREFERENCES`
- `COMPONENT1_WEIGHTS`
