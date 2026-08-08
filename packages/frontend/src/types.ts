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
  access_token: string | null;
  token_type: string;
  expires_in: number;
  user: User;
  token_transport: "bearer" | "cookie";
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

export interface Component4CandidateHandoff {
  source: "component2" | "development_fixture";
  request_id: string;
  user_id: string;
  component_version: string;
  model_version: string;
  provider_ids: string[];
}

export type Component4HandoffLineage = Omit<
  Component4CandidateHandoff,
  "provider_ids"
>;

export interface Component4AspectScores {
  quality: number;
  punctuality: number;
  communication: number;
  professionalism: number;
}

export interface Component4Versions {
  catf_version: string;
  weight_version: string;
  category_prior_version: string;
  absa_model_version: string;
  credibility_model_version: string;
}

export interface Component4RankedProvider {
  provider_id: string;
  provider_name: string;
  category: string;
  district: string;
  city: string;
  rank: number;
  final_score: number;
  aspect_scores: Component4AspectScores;
  mean_credibility: number;
  review_count: number;
  effective_review_count: number;
  reliability_factor: number;
  evidence_status: "insufficient" | "limited" | "sufficient";
  score_source: "catf_evidence" | "category_prior";
  platform_rating: number;
  platform_review_count: number;
}

export interface Component4RankResponse {
  component_version: string;
  request_id: string;
  run_id: string;
  user_id: string;
  handoff: Component4HandoffLineage;
  input_count: number;
  output_count: number;
  requested_top_k: number;
  candidate_provider_ids: string[];
  providers: Component4RankedProvider[];
  versions: Component4Versions;
  cached: boolean;
  processing_time_ms: number;
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

export interface ProviderAspectPerformance {
  quality: number;
  communication: number;
  professionalism: number;
  punctuality: number;
}

export interface ProviderCustomerReview {
  rating: number;
  review_text: string | null;
  reviewed_at: string;
  verified_booking: boolean;
  source: "platform" | "research_dataset";
  credibility_score: number | null;
}

export interface ProviderTrustProfile {
  provider_id: string;
  provider_name: string;
  category: string;
  district: string;
  city: string;
  description: string;
  skills: string[];
  experience_years: number;
  average_rating: number;
  review_count: number;
  overall_trust_score: number;
  aspect_performance: ProviderAspectPerformance;
  mean_review_credibility: number;
  analyzed_review_count: number;
  evidence_status: "insufficient" | "limited" | "sufficient";
  score_source: "catf_evidence" | "category_prior";
  customer_reviews: ProviderCustomerReview[];
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
  review_text: string | null;
  timestamp: string;
}

export interface AdminOverview {
  users: number;
  providers: number;
  service_requests: number;
  interactions: number;
}
