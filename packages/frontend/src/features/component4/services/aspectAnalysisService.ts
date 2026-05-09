import type {
  AnalyzeResponse,
  BatchAnalyzeResponse,
  ReviewCredibilityResponse,
  ProviderCredibility,
  RankProvidersResponse,
  PipelineRunResponse,
} from "../types";

const API_BASE = "http://localhost:8000/api/v1";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function analyzeReview(text: string): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/component4/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  return handleResponse<AnalyzeResponse>(res);
}

export async function analyzeReviewBatch(texts: string[]): Promise<BatchAnalyzeResponse> {
  const res = await fetch(`${API_BASE}/component4/analyze/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texts }),
  });
  return handleResponse<BatchAnalyzeResponse>(res);
}

export type ReviewBehavioral = {
  rating?: number;
  user_total_reviews?: number;
  days_since_prev_review?: number;
  user_provider_diversity?: number;
  text_frequency?: number;
  days_since_review?: number;
  booking_status?: number;
};

export async function analyzeReviewCredibility(
  text: string,
  behavioral?: ReviewBehavioral
): Promise<ReviewCredibilityResponse> {
  const res = await fetch(`${API_BASE}/component4/review/credibility`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, behavioral: behavioral ?? null }),
  });
  return handleResponse<ReviewCredibilityResponse>(res);
}

export async function getProviderCredibility(providerId: string): Promise<ProviderCredibility> {
  const res = await fetch(`${API_BASE}/component4/provider/${encodeURIComponent(providerId)}/credibility`);
  return handleResponse<ProviderCredibility>(res);
}

export async function rankProviders(providerIds: string[]): Promise<RankProvidersResponse> {
  const res = await fetch(`${API_BASE}/component4/providers/rank`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider_ids: providerIds }),
  });
  return handleResponse<RankProvidersResponse>(res);
}

/** Run the Component 3 → 4 pipeline.
 *  Pass providerIds from Component 3, or omit to use a random sample. */
export async function runPipeline(providerIds?: string[], topN = 5): Promise<PipelineRunResponse> {
  if (providerIds && providerIds.length > 0) {
    const res = await fetch(`${API_BASE}/component4/pipeline/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider_ids: providerIds, top_n: topN }),
    });
    return handleResponse<PipelineRunResponse>(res);
  }
  const res = await fetch(`${API_BASE}/component4/pipeline/run`);
  return handleResponse<PipelineRunResponse>(res);
}
