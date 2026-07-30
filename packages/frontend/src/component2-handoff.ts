import type { RecommendationResponse } from "./types";

export const COMPONENT2_HANDOFF_MODE =
  import.meta.env.VITE_COMPONENT2_HANDOFF_MODE ?? "component1-top10-fixture";

export function buildComponent2IntegrationFixture(
  recommendations: RecommendationResponse,
): string[] {
  return Array.from(
    new Set(recommendations.results.map((provider) => provider.provider_id)),
  ).slice(0, 10);
}
