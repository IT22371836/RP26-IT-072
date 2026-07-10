"""
Flask API for Hybrid Recommendation System
Production-ready service for ranking providers

Usage:
    python app.py
    
Then call endpoints:
    POST /recommend
    POST /recommend/batch
    GET  /health
    GET  /provider/<provider_id>
"""

from flask import Flask, request, jsonify
import logging
import json
from datetime import datetime
from typing import Dict, Optional

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Global recommender instance (will be initialized from notebook)
recommender = None
provider_df = None

def init_recommender(rec_instance, prov_df):
    """Initialize recommender on app startup"""
    global recommender, provider_df
    recommender = rec_instance
    provider_df = prov_df
    logger.info("✓ Recommender initialized from notebook components")

# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint - verify service is running"""
    return jsonify({
        'status': 'healthy',
        'service': 'hybrid-recommender',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    }), 200

@app.route('/status', methods=['GET'])
def status():
    """Get system status and configuration"""
    return jsonify({
        'status': 'ready',
        'recommender_loaded': recommender is not None,
        'total_providers': len(provider_df) if provider_df is not None else 0,
        'weights': {
            'tfidf': 0.30,
            'bert': 0.40,
            'cf': 0.30
        },
        'timestamp': datetime.now().isoformat()
    }), 200

# ============================================================================
# RECOMMENDATION ENDPOINTS
# ============================================================================

@app.route('/recommend', methods=['POST'])
def recommend():
    """
    Main recommendation endpoint - returns top providers for a query
    
    Request format:
    {
        "query": "web development",
        "user_id": 123,
        "top_k": 20,              (optional, default: 20)
        "min_rating": 4.0,        (optional, default: 0.0)
        "max_price": 500,         (optional, default: None)
        "location": "New York"    (optional, default: None)
    }
    
    Response format:
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
                    "tfidf": 0.75,
                    "bert": 0.85,
                    "cf": 0.82
                },
                "engagement": {
                    "interaction_count": 150,
                    "booking_success_rate": 0.92
                }
            },
            ...
        ],
        "weights_used": {"tfidf": 0.30, "bert": 0.40, "cf": 0.30}
    }
    """
    try:
        if recommender is None:
            return jsonify({'error': 'Recommender not initialized'}), 503
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Extract and validate required fields
        query = data.get('query', '').strip()
        user_id = data.get('user_id')
        
        if not query:
            return jsonify({'error': 'Query cannot be empty'}), 400
        
        if user_id is None:
            return jsonify({'error': 'user_id is required'}), 400
        
        # Extract optional parameters
        top_k = int(data.get('top_k', 20))
        min_rating = float(data.get('min_rating', 0.0))
        max_price = data.get('max_price')
        location = data.get('location')
        
        # Validate parameters
        if top_k <= 0 or top_k > 100:
            return jsonify({'error': 'top_k must be between 1 and 100'}), 400
        
        if min_rating < 0 or min_rating > 5:
            return jsonify({'error': 'min_rating must be between 0 and 5'}), 400
        
        max_price = float(max_price) if max_price else None
        if max_price and max_price < 0:
            return jsonify({'error': 'max_price cannot be negative'}), 400
        
        logger.info(f"Recommendation request - Query: '{query}' (user: {user_id}, top_k: {top_k})")
        
        # Get recommendations from the recommender
        result = recommender.recommend(
            query=query,
            user_id=int(user_id),
            top_k=top_k,
            min_rating=min_rating,
            max_price=max_price,
            location=location
        )
        
        if result['status'] == 'error':
            logger.error(f"Recommendation error: {result.get('message')}")
            return jsonify(result), 400
        
        logger.info(f"✓ Returned {result['total_results']} recommendations")
        return jsonify(result), 200
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return jsonify({'error': f'Invalid parameters: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error in /recommend: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500

@app.route('/recommend/batch', methods=['POST'])
def recommend_batch():
    """
    Batch recommendation endpoint - get recommendations for multiple queries
    
    Request format:
    {
        "user_id": 123,
        "queries": ["web development", "graphic design", "marketing"],
        "top_k": 10
    }
    """
    try:
        if recommender is None:
            return jsonify({'error': 'Recommender not initialized'}), 503
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        user_id = data.get('user_id')
        queries = data.get('queries', [])
        top_k = int(data.get('top_k', 10))
        
        if user_id is None:
            return jsonify({'error': 'user_id is required'}), 400
        
        if not isinstance(queries, list) or len(queries) == 0:
            return jsonify({'error': 'queries must be a non-empty list'}), 400
        
        if len(queries) > 20:
            return jsonify({'error': 'Maximum 20 queries allowed per batch'}), 400
        
        logger.info(f"Batch recommendation request - {len(queries)} queries for user {user_id}")
        
        results = []
        for query in queries:
            result = recommender.recommend(
                query=query.strip(),
                user_id=int(user_id),
                top_k=top_k
            )
            results.append({
                'query': query,
                'result': result
            })
        
        response = {
            'status': 'success',
            'user_id': user_id,
            'batch_size': len(results),
            'timestamp': datetime.now().isoformat(),
            'results': results
        }
        
        logger.info(f"✓ Batch recommendation completed for {len(results)} queries")
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error in /recommend/batch: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================================================
# PROVIDER ENDPOINTS
# ============================================================================

@app.route('/provider/<int:provider_id>', methods=['GET'])
def get_provider_details(provider_id):
    """Get detailed information about a specific provider"""
    try:
        if provider_df is None:
            return jsonify({'error': 'Provider data not initialized'}), 503
        
        provider = provider_df[provider_df['provider_id'] == provider_id]
        
        if provider.empty:
            return jsonify({'error': f'Provider {provider_id} not found'}), 404
        
        provider_data = provider.iloc[0].to_dict()
        
        return jsonify({
            'status': 'success',
            'provider': provider_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching provider: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/providers/search', methods=['GET'])
def search_providers():
    """Search providers by name or service"""
    try:
        if provider_df is None:
            return jsonify({'error': 'Provider data not initialized'}), 503
        
        query = request.args.get('q', '').lower()
        limit = int(request.args.get('limit', 10))
        
        if not query:
            return jsonify({'error': 'Search query required'}), 400
        
        if limit > 100:
            limit = 100
        
        # Search in provider name and service
        mask = (provider_df['provider_name'].str.lower().str.contains(query, na=False) |
                provider_df['service'].str.lower().str.contains(query, na=False))
        
        results = provider_df[mask].head(limit)
        
        return jsonify({
            'status': 'success',
            'query': query,
            'count': len(results),
            'providers': results[['provider_id', 'provider_name', 'service', 'rating', 'price']].to_dict('records')
        }), 200
        
    except Exception as e:
        logger.error(f"Error in /providers/search: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found',
        'path': request.path
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("HYBRID RECOMMENDATION SYSTEM - Flask API")
    logger.info("=" * 80)
    logger.info("Starting server on http://0.0.0.0:5000")
    logger.info("\nAPI Endpoints:")
    logger.info("  GET  /health                    - Health check")
    logger.info("  GET  /status                    - System status")
    logger.info("  POST /recommend                 - Get recommendations")
    logger.info("  POST /recommend/batch           - Batch recommendations")
    logger.info("  GET  /provider/<id>             - Provider details")
    logger.info("  GET  /providers/search          - Search providers")
    logger.info("=" * 80 + "\n")
    
    # Start Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
