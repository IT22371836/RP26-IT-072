import { describe, expect, it } from "vitest";
import { buildComponent2IntegrationFixture } from "./component2-handoff";
import type { ProviderRecommendation, RecommendationResponse } from "./types";


function provider(providerId: string): ProviderRecommendation {
  return {
    provider_id: providerId,
    provider_name: providerId,
    category: "Electricians",
    district: "Colombo",
    city: "Kottawa",
    skills: "wiring",
    description: "Test provider",
    experience_years: 5,
    rating: 4.5,
    review_count: 10,
    booking_success_rate: 0.9,
    interaction_count: 15,
    hybrid_score: 0.8,
    tfidf_score: 0.8,
    bert_score: 0.8,
    cf_score: 0.8,
  };
}


function recommendation(providerIds: string[]): RecommendationResponse {
  return {
    component_version: "1.0.0",
    model_version: "component1-test",
    request_id: "RTEST1",
    query: "electrician",
    user_id: "UTEST1",
    results: providerIds.map(provider),
  };
}


describe("Component 2 integration fixture", () => {
  it("hands exactly the first ten unique Component 1 IDs to Component 4", () => {
    const result = buildComponent2IntegrationFixture(
      recommendation(Array.from({ length: 20 }, (_, index) => `P${index + 1}`)),
    );

    expect(result).toHaveLength(10);
    expect(result).toEqual(Array.from({ length: 10 }, (_, index) => `P${index + 1}`));
  });

  it("removes duplicate IDs without inventing candidates", () => {
    const result = buildComponent2IntegrationFixture(
      recommendation(["P1", "P1", "P2", "P3"]),
    );

    expect(result).toEqual(["P1", "P2", "P3"]);
  });
});
