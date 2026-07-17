export type UserRole = "customer" | "provider" | "admin";
export type Urgency = "normal" | "urgent" | "emergency";

export interface User {
  user_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface ServiceRequestInput {
  request_text: string;
  category: string;
  district: string;
  city: string;
  urgency: Urgency;
}

export interface ServiceRequest extends ServiceRequestInput {
  request_id: string;
  user_id: string;
  created_at: string;
}

export interface ProviderRecommendation {
  provider_id: string;
  provider_name: string;
  category: string;
  district: string;
  city: string;
  skills: string;
  description: string;
  experience_years: number;
  rating: number;
  review_count: number;
  booking_success_rate: number;
  interaction_count: number;
  hybrid_score: number;
  tfidf_score: number;
  bert_score: number;
  cf_score: number;
}

export interface RecommendationResponse {
  component_version: string;
  model_version: string;
  request_id: string;
  query: string;
  user_id: string;
  results: ProviderRecommendation[];
}
