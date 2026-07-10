import type { AnalyzeResponse, BatchAnalyzeResponse } from "../types";

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
