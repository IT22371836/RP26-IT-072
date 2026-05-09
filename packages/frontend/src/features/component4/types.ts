export type TokenTag = {
  token: string;
  tag: string;
};

export type AspectScores = {
  QUAL: number | null;
  PRICE: number | null;
  TIME: number | null;
  COMM: number | null;
};

export type AnalyzeResponse = {
  status: string;
  text: string;
  tokens: TokenTag[];
  aspects: AspectScores;
  timestamp: string;
};

export type BatchResultItem = {
  text: string;
  result: AnalyzeResponse;
};

export type BatchAnalyzeResponse = {
  status: string;
  batch_size: number;
  timestamp: string;
  results: BatchResultItem[];
};

// ─── Fraud / Credibility types ────────────────────────────────────────────────

export type LinguisticFeatures = {
  word_count: number;
  unique_word_ratio: number;
  pronoun_count: number;
  adj_density: number;
  exclamation_count: number;
  caps_ratio: number;
  rating_text_mismatch: number;
};

export type ReviewCredibilityResponse = {
  status: string;
  text: string;
  tokens: TokenTag[];
  aspects: AspectScores;
  fraud_score: number;
  trust_label: "Verified" | "Unverified" | "Suspicious";
  is_suspicious: boolean;
  linguistic_features: LinguisticFeatures;
  timestamp: string;
};

export type ProviderCredibility = {
  provider_id: string;
  S_final: number;
  tier: "Elite" | "Trusted" | "Verified" | "Unknown";
  S_cred?: number | null;
  S_overall?: number | null;
  fraud_ratio?: number | null;
  recency_boost?: number | null;
  avg_rating?: number | null;
  total_reviews?: number | null;
  suspicious_count?: number | null;
  explanation?: string | null;
};

export type ProviderRankEntry = ProviderCredibility & { rank: number };

export type RankProvidersResponse = {
  status: string;
  total: number;
  ranked: ProviderRankEntry[];
  timestamp: string;
};

export type PipelineRunResponse = {
  status: string;
  source: "random" | "component3";
  providers_evaluated: number;
  top_n: number;
  ranked: ProviderRankEntry[];
  note: string;
  timestamp: string;
};
