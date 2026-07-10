import type {
  Component1Status,
  RecommendBatchRequest,
  RecommendBatchResponse,
  RecommendRequest,
  RecommendResponse,
} from "../types";

const API_BASE = "http://localhost:8000/api/v1";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function getComponent1Status(): Promise<Component1Status> {
  const res = await fetch(`${API_BASE}/component1/status`);
  return handleResponse<Component1Status>(res);
}

export async function recommendProviders(payload: RecommendRequest): Promise<RecommendResponse> {
  const res = await fetch(`${API_BASE}/component1/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<RecommendResponse>(res);
}

export async function recommendProvidersBatch(
  payload: RecommendBatchRequest,
): Promise<RecommendBatchResponse> {
  const res = await fetch(`${API_BASE}/component1/recommend/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<RecommendBatchResponse>(res);
}
