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

export interface ProviderProfileInput {
  provider_name: string;
  category: string;
  district: string;
  city: string;
  experience_years: number;
  skills: string[];
  description: string;
}

export interface ProviderProfile extends ProviderProfileInput {
  provider_id: string;
  user_id: string;
  rating: number;
  review_count: number;
  booking_success_rate: number;
  interaction_count: number;
  created_at: string;
  updated_at: string;
}

export interface CustomerProfileUpdate {
  phone: string | null;
  district: string | null;
  city: string | null;
  preferred_language: string;
}

export interface CustomerProfile extends CustomerProfileUpdate {
  customer_id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export type InteractionType =
  | "impression"
  | "click"
  | "selected"
  | "booking_requested"
  | "booking_completed"
  | "booking_cancelled"
  | "rated";

export interface Interaction {
  interaction_id: string;
  request_id: string;
  user_id: string;
  provider_id: string;
  provider_name: string | null;
  category: string;
  interaction_type: InteractionType;
  rating: number | null;
  timestamp: string;
}

export interface AdminOverview {
  users: number;
  providers: number;
  service_requests: number;
  interactions: number;
}
