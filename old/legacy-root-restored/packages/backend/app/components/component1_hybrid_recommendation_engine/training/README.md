# Hybrid Recommendation System for Service Marketplace

A production-ready recommendation engine that combines TF-IDF, BERT embeddings, and collaborative filtering to rank service providers based on user queries.

## 📋 Overview

This system implements **Component 1: Service Provider Ranking** of a marketplace platform, designed to return the top 20 best-matching providers for any user query.

### Architecture
```
User Query
    ↓
    ├─→ TF-IDF (30%) → Keyword matching
    ├─→ BERT (40%) → Semantic understanding  
    └─→ CF (30%) → User preferences & credibility
    ↓
[Weighted Combination + Normalization]
    ↓
Top 20 Ranked Providers
```

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.8+
- 4GB RAM (minimum), 8GB recommended
- 5GB disk space for model and data

### 2. Installation

```bash
# Install required packages
pip install pandas numpy scikit-learn sentence-transformers scipy

# Optional: For Flask API
pip install flask

# Optional: For production server
pip install gunicorn
```

### 3. Dataset Preparation

Place your datasets in the project directory:
- `provider_dataset_100k.xlsx` - Provider information
- `user_interaction_dataset_120k.xlsx` - User-provider interactions

### 4. Run the Notebook

```bash
# Open and run the Jupyter notebook
jupyter notebook hybrid_recommendation_system.ipynb
```

### 5. Deploy Flask API (Optional)

```bash
# Start the API server
python app.py

# For production with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📊 Dataset Format

### Provider Dataset
```
Columns:
- provider_id (int): Unique provider identifier
- provider_name (str): Provider's business name
- service (str): Type of service offered
- description (str): Detailed service description
- experience_years (int): Years of experience
- location (str): Geographic location
- price (float): Hourly/project rate
- rating (float): Average rating (0-5)
```

### User Interaction Dataset
```
Columns:
- user_id (int): Unique user identifier
- provider_id (int): Provider they interacted with
- rating (float): Rating given by user (0-5)
- booking_status (str): "completed" or "pending"
- review_text (str): Optional review text
- timestamp (datetime): Interaction timestamp
```

## 🔧 System Components

### 1. TF-IDF Component (Weight: 30%)
- **Purpose**: Keyword-level relevance matching
- **Implementation**: sklearn TfidfVectorizer
- **Strengths**: Fast, explainable, good for exact matches
- **Example**: Query "web developer" matches "web development services"

### 2. BERT Component (Weight: 40%)
- **Purpose**: Semantic understanding and meaning
- **Implementation**: sentence-transformers all-minilm-l6-v2
- **Strengths**: Understands synonyms, context, relationships
- **Example**: Query "app developer" matches "iOS/Android development"

### 3. Collaborative Filtering (Weight: 30%)
- **Purpose**: User preferences and provider credibility
- **Implementation**: Rating history + booking success rate
- **Strengths**: Personalizes results, identifies trusted providers
- **Formula**: (rating/5 × 0.5) + (success_rate × 0.3) + (engagement × 0.2)

## 📈 Performance Characteristics

| Metric | Value |
|--------|-------|
| Response Time | 50-200ms per query |
| Memory Usage | 2-3GB for 100k providers |
| Model Size | ~91MB (BERT) + 50MB (TF-IDF) |
| Scalability | Linear with provider count |
| Supports | 100k+ providers efficiently |

## 🎯 Usage Examples

### Python Notebook
```python
# Initialize recommender
recommender = HybridRecommender(
    tfidf_vectorizer=tfidf_vectorizer,
    bert_model=bert_model,
    provider_df=provider_df,
    cf_scores_fn=compute_cf_scores
)

# Get recommendations
results = recommender.recommend(
    query="web development",
    user_id=123,
    top_k=20,
    min_rating=4.0,
    max_price=500,
    location="New York"
)

# Access results
for rec in results['recommendations'][:5]:
    print(f"{rec['provider_name']}: {rec['scores']['hybrid']:.4f}")
```

### Flask API

#### Single Recommendation
```bash
curl -X POST http://localhost:5000/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "query": "web development",
    "user_id": 123,
    "top_k": 20,
    "min_rating": 4.0,
    "max_price": 500
  }'
```

#### Batch Recommendations
```bash
curl -X POST http://localhost:5000/recommend/batch \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "queries": ["web development", "graphic design"],
    "top_k": 10
  }'
```

#### Health Check
```bash
curl http://localhost:5000/health
```

#### Provider Details
```bash
curl http://localhost:5000/provider/42
```

## 📊 Response Format

```json
{
  "status": "success",
  "query": "web development",
  "user_id": 123,
  "total_results": 20,
  "recommendations": [
    {
      "rank": 1,
      "provider_id": 42,
      "provider_name": "John's Web Solutions",
      "service": "web development",
      "location": "San Francisco",
      "rating": 4.8,
      "price": 250.00,
      "experience_years": 5,
      "scores": {
        "hybrid": 0.8234,
        "tfidf": 0.7500,
        "bert": 0.8500,
        "cf": 0.8200
      },
      "engagement": {
        "interaction_count": 150,
        "booking_success_rate": 0.92
      }
    }
  ],
  "weights_used": {
    "tfidf": 0.30,
    "bert": 0.40,
    "cf": 0.30
  }
}
```

## 🔧 Configuration

### Adjust Component Weights
Edit weights in notebook or `app.py`:
```python
WEIGHTS = {
    'tfidf': 0.30,    # Keyword matching
    'bert': 0.40,     # Semantic understanding
    'cf': 0.30        # User preferences
}
```

### TF-IDF Parameters
```python
TfidfVectorizer(
    max_features=5000,      # Vocabulary size
    min_df=2,               # Minimum document frequency
    max_df=0.8,             # Maximum document frequency
    ngram_range=(1, 2)      # Unigrams + bigrams
)
```

## 🚀 Production Deployment

### 1. Precompute Embeddings
```python
# Run once to precompute all BERT embeddings
provider_embeddings = bert_model.encode(
    provider_df['combined_text'].tolist(),
    batch_size=128,
    show_progress_bar=True
)
# Save with pickle or joblib for fast loading
```

### 2. Caching Strategy
```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def get_recommendations_cached(query, user_id):
    return recommender.recommend(query, user_id)
```

### 3. Load Balancing
```bash
# Run multiple Flask instances
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Or use Docker
docker build -t recommender .
docker run -d -p 5000:5000 recommender
```

### 4. Monitoring
- Track API response times
- Log recommendation quality metrics
- Monitor BERT model latency
- Alert on error rates > 5%

## 📈 Optimization Tips

1. **Batch Processing**: Use `/recommend/batch` for multiple queries
2. **Prefilter**: Apply price/location filters before ranking
3. **Caching**: Cache embeddings and precompute CF scores daily
4. **Model Quantization**: Use quantized BERT for faster inference
5. **GPU Acceleration**: Deploy on GPU for 10x+ speedup

## 🔍 Debugging

### Check Component Contributions
```python
# See individual component scores
results = recommender.recommend("query", user_id)
for rec in results['recommendations'][:1]:
    print(f"BERT: {rec['scores']['bert']}")
    print(f"TF-IDF: {rec['scores']['tfidf']}")
    print(f"CF: {rec['scores']['cf']}")
    print(f"Hybrid: {rec['scores']['hybrid']}")
```

### Validate Provider Data
```python
# Check for missing values
print(provider_df.isnull().sum())

# Verify embeddings shape
print(provider_embeddings.shape)

# Test TF-IDF vectorizer
print(tfidf_vectorizer.get_feature_names_out()[:10])
```

## 📚 Advanced Usage

### Custom Filtering
```python
# Filter by multiple criteria
results = rank_providers(
    query="development",
    user_id=123,
    top_k=20,
    min_rating=4.5,
    max_price=300,
    location="California"
)
```

### A/B Testing
```python
# Compare different weight configurations
weights_v1 = {'tfidf': 0.3, 'bert': 0.4, 'cf': 0.3}
weights_v2 = {'tfidf': 0.2, 'bert': 0.5, 'cf': 0.3}

# Test both and measure user engagement
```

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| BERT model not found | Run `download_model.py` to fetch model |
| OOM error with large dataset | Process providers in batches |
| Slow API responses | Enable GPU, use batch endpoints |
| Inaccurate results | Adjust component weights |
| Cold-start problem | Pre-compute recommendations for new users |

## 📦 Files in This Project

```
model-test/
├── hybrid_recommendation_system.ipynb  # Main notebook
├── app.py                              # Flask API
├── download_model.py                   # BERT model downloader
├── provider_dataset_100k.xlsx          # Provider data
├── user_interaction_dataset_120k.xlsx  # Interaction data
├── requirements.txt                    # Python dependencies
├── models/                             # Local BERT model cache
└── README.md                           # This file
```

## 🤝 Contributing

To improve the system:
1. Adjust weights based on user feedback
2. Add new filtering criteria
3. Implement more sophisticated CF algorithms
4. Test with different BERT models
5. Optimize for your specific use case

## 📄 License

This implementation is provided as-is for educational and commercial use.

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review notebook cells for detailed explanations
3. Inspect API error messages in logs
4. Adjust weights and parameters for your use case

---

**Built for scalable service marketplace recommendations** 🚀
