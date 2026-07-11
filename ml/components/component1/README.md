# Component 1 - Hybrid Recommendation Engine

Owner workspace for TF-IDF, multilingual Sentence Transformer, credibility-based collaborative filtering, and hybrid Top-20 retrieval.

Current supplied inputs:

- 10,000 provider records
- 100,000 user interaction records
- 20,000 user request records
- Google Colab training/evaluation notebook

The notebook currently exports evaluation CSV and PNG files, but not all artifacts required by a backend inference service. Before integration it must export fitted TF-IDF state, provider vectors/embeddings, collaborative-filtering state, provider lookup data, weights, and an artifact manifest.
