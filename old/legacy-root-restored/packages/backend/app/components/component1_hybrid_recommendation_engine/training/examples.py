#!/usr/bin/env python3
"""
Example: Using the Hybrid Recommendation System
This script demonstrates how to use the recommender outside of Jupyter
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Note: Run the notebook first to generate the required components
# This script assumes you have access to the precomputed components

def example_basic_usage():
    """Example 1: Basic recommendation for a single query"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic Single Query Recommendation")
    print("="*80)
    
    # These would be loaded from the notebook execution
    # recommender.recommend(query, user_id, top_k)
    
    print("""
    # Get recommendations for a single query
    result = recommender.recommend(
        query="web development services",
        user_id=123,
        top_k=20
    )
    
    # Access top 5 results
    for rec in result['recommendations'][:5]:
        print(f"#{rec['rank']} - {rec['provider_name']}")
        print(f"   Score: {rec['scores']['hybrid']:.4f}")
        print(f"   Rating: {rec['rating']}/5.0")
        print(f"   Price: ${rec['price']:.2f}")
    """)

def example_filtered_search():
    """Example 2: Search with filters"""
    print("\n" + "="*80)
    print("EXAMPLE 2: Filtered Search")
    print("="*80)
    
    print("""
    # Get recommendations with filters
    result = recommender.recommend(
        query="graphic design",
        user_id=123,
        top_k=20,
        min_rating=4.5,      # Only highly-rated providers
        max_price=300,       # Budget constraint
        location="New York"  # Geographic filter
    )
    
    print(f"Found {result['total_results']} providers matching criteria")
    """)

def example_batch_queries():
    """Example 3: Batch processing multiple queries"""
    print("\n" + "="*80)
    print("EXAMPLE 3: Batch Query Processing")
    print("="*80)
    
    print("""
    # Get recommendations for multiple queries at once
    from concurrent.futures import ThreadPoolExecutor
    
    queries = [
        "web development",
        "graphic design",
        "digital marketing",
        "SEO services"
    ]
    
    results = []
    for query in queries:
        result = recommender.recommend(query, user_id=123, top_k=10)
        results.append(result)
    
    # Or using batch API for faster processing
    result = recommender.recommend_batch(
        queries=queries,
        user_id=123,
        top_k=10
    )
    """)

def example_score_analysis():
    """Example 4: Analyze component scores"""
    print("\n" + "="*80)
    print("EXAMPLE 4: Understanding Component Scores")
    print("="*80)
    
    print("""
    # Get recommendation and analyze component contributions
    result = recommender.recommend("web development", user_id=123, top_k=1)
    rec = result['recommendations'][0]
    
    print(f"Provider: {rec['provider_name']}")
    print(f"Query Match Scores:")
    print(f"  - Keyword Match (TF-IDF):      {rec['scores']['tfidf']:.2%} (30% weight)")
    print(f"  - Semantic Match (BERT):       {rec['scores']['bert']:.2%} (40% weight)")
    print(f"  - Credibility (Collab Filter): {rec['scores']['cf']:.2%} (30% weight)")
    print(f"  ────────────────────────────────────")
    print(f"  - Final Hybrid Score:          {rec['scores']['hybrid']:.2%}")
    """)

def example_personalization():
    """Example 5: How personalization works"""
    print("\n" + "="*80)
    print("EXAMPLE 5: Personalization with Collaborative Filtering")
    print("="*80)
    
    print("""
    # Same query, different users get different results
    
    user1_results = recommender.recommend("design services", user_id=1, top_k=5)
    user2_results = recommender.recommend("design services", user_id=2, top_k=5)
    
    # User1 sees providers they've worked with before (boosted)
    # User2 sees highest-rated providers in the network
    
    # Collaborative Filtering Component Score Breakdown:
    # CF Score = (rating/5 * 0.5) + (booking_success_rate * 0.3) + (engagement * 0.2)
    
    print("User 1 top result:", user1_results['recommendations'][0]['provider_name'])
    print("User 2 top result:", user2_results['recommendations'][0]['provider_name'])
    """)

def example_using_flask_api():
    """Example 6: Using Flask API"""
    print("\n" + "="*80)
    print("EXAMPLE 6: REST API Usage")
    print("="*80)
    
    print("""
    import requests
    
    API_URL = "http://localhost:5000"
    
    # Health check
    response = requests.get(f"{API_URL}/health")
    print(response.json())
    
    # Single recommendation
    payload = {
        "query": "web development",
        "user_id": 123,
        "top_k": 20,
        "min_rating": 4.0
    }
    response = requests.post(f"{API_URL}/recommend", json=payload)
    results = response.json()
    
    # Batch recommendations
    payload = {
        "user_id": 123,
        "queries": ["web development", "graphic design"],
        "top_k": 10
    }
    response = requests.post(f"{API_URL}/recommend/batch", json=payload)
    results = response.json()
    
    # Provider search
    response = requests.get(f"{API_URL}/providers/search?q=web+developer&limit=10")
    results = response.json()
    """)

def example_optimization():
    """Example 7: Optimization for production"""
    print("\n" + "="*80)
    print("EXAMPLE 7: Production Optimizations")
    print("="*80)
    
    print("""
    # 1. Precompute embeddings for all providers
    all_embeddings = bert_model.encode(
        provider_df['combined_text'].tolist(),
        batch_size=256,
        show_progress_bar=True
    )
    
    # 2. Cache frequent queries
    from functools import lru_cache
    
    @lru_cache(maxsize=10000)
    def get_cached_recommendations(query, user_id):
        return recommender.recommend(query, user_id)
    
    # 3. Use batch processing for multiple queries
    queries = [...]  # 100 queries
    results = [recommender.recommend(q, 123) for q in queries]
    
    # 4. Monitor performance
    import time
    start = time.time()
    result = recommender.recommend("web development", 123)
    elapsed = time.time() - start
    print(f"Query took {elapsed*1000:.2f}ms")
    """)

def example_monitoring():
    """Example 8: Monitoring and quality checks"""
    print("\n" + "="*80)
    print("EXAMPLE 8: Monitoring & Quality Checks")
    print("="*80)
    
    print("""
    # Check recommendation quality metrics
    result = recommender.recommend("web development", user_id=123, top_k=20)
    
    # Score distribution
    scores = [r['scores']['hybrid'] for r in result['recommendations']]
    print(f"Mean score: {np.mean(scores):.4f}")
    print(f"Score range: [{min(scores):.4f}, {max(scores):.4f}]")
    
    # Diversity check (how different are top results)
    top_3_names = [r['provider_name'] for r in result['recommendations'][:3]]
    print(f"Top 3 providers: {top_3_names}")
    
    # Component analysis
    tfidf_scores = [r['scores']['tfidf'] for r in result['recommendations']]
    bert_scores = [r['scores']['bert'] for r in result['recommendations']]
    cf_scores = [r['scores']['cf'] for r in result['recommendations']]
    
    print(f"Average TF-IDF: {np.mean(tfidf_scores):.4f}")
    print(f"Average BERT: {np.mean(bert_scores):.4f}")
    print(f"Average CF: {np.mean(cf_scores):.4f}")
    """)

def example_integration():
    """Example 9: Integration with web application"""
    print("\n" + "="*80)
    print("EXAMPLE 9: Web Application Integration")
    print("="*80)
    
    print("""
    # In your web application (Django, FastAPI, etc.)
    
    # Step 1: User submits search
    user_id = request.session.get('user_id')
    query = request.GET.get('q')
    
    # Step 2: Get recommendations
    result = recommender.recommend(
        query=query,
        user_id=user_id,
        top_k=20
    )
    
    # Step 3: Render results
    recommendations = result['recommendations']
    
    # Step 4: Track which provider user clicks
    # (This data helps improve CF component)
    user_clicked_provider_id = request.GET.get('provider_id')
    log_user_interaction(user_id, user_clicked_provider_id)
    """)

def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("HYBRID RECOMMENDATION SYSTEM - USAGE EXAMPLES")
    print("="*80)
    
    examples = [
        ("Basic Usage", example_basic_usage),
        ("Filtered Search", example_filtered_search),
        ("Batch Queries", example_batch_queries),
        ("Score Analysis", example_score_analysis),
        ("Personalization", example_personalization),
        ("Flask API", example_using_flask_api),
        ("Optimizations", example_optimization),
        ("Monitoring", example_monitoring),
        ("Web Integration", example_integration),
    ]
    
    for i, (name, func) in enumerate(examples, 1):
        func()
    
    print("\n" + "="*80)
    print("QUICK START")
    print("="*80)
    print("""
    1. Run the Jupyter notebook:
       jupyter notebook hybrid_recommendation_system.ipynb
    
    2. For Flask API usage:
       python app.py
       
    3. Check out the README.md for more details
    
    4. Try these queries in the notebook:
       - "web development"
       - "graphic design"
       - "marketing consultant"
       - "business consulting"
    """)
    print("="*80 + "\n")

if __name__ == '__main__':
    main()
