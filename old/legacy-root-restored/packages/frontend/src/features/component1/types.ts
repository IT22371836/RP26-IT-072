export type RecommendRequest = {
  query: string;
  user_id: number;
  top_k?: number;
  min_rating?: number;
  max_price?: number | null;
  location?: string | null;
};

export type RecommendationScores = {
  hybrid: number;
  tfidf: number;
  bert: number;
  cf: number;
};

export type RecommendationEngagement = {
  interaction_count: number;
  booking_success_rate: number;
};

export type RecommendationItem = {
  rank: number;
  provider_id: string;
  provider_name: string;
  service: string;
  location: string;
  rating: number;
  price: number;
  experience_years: number;
  scores: RecommendationScores;
  engagement: RecommendationEngagement;
};

export type RecommendResponse = {
  status: string;
  query: string;
  user_id: string;
  timestamp: string;
  total_results: number;
  recommendations: RecommendationItem[];
  weights_used: Record<string, number>;
};

export type RecommendBatchRequest = {
  user_id: number;
  queries: string[];
  top_k?: number;
};

export type BatchResult = {
  query: string;
  result: RecommendResponse;
};

export type RecommendBatchResponse = {
  status: string;
  user_id: number;
  batch_size: number;
  timestamp: string;
  results: BatchResult[];
};

export type Component1Status = {
  status: string;
  recommender_loaded: boolean;
  total_providers: number;
  weights: Record<string, number>;
  timestamp: string;
};
