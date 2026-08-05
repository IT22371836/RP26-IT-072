import { describe, expect, it } from "vitest";
import {
  Component2HandoffError,
  buildComponent2IntegrationFixture,
  getComponent2HandoffReadiness,
  validateComponent4CandidateHandoff,
} from "./component2-handoff";
import type {
  Component4CandidateHandoff,
  ProviderRecommendation,
  RecommendationResponse,
} from "./types";


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
    const component1 = recommendation(
      Array.from({ length: 20 }, (_, index) => `P${index + 1}`),
    );
    const handoff = buildComponent2IntegrationFixture(component1);
    const result = validateComponent4CandidateHandoff(handoff, component1, false);

    expect(result).toHaveLength(10);
    expect(result).toEqual(Array.from({ length: 10 }, (_, index) => `P${index + 1}`));
    expect(handoff.source).toBe("development_fixture");
  });

  it("removes duplicate IDs without inventing candidates", () => {
    const component1 = recommendation(["P1", "P1", "P2", "P3"]);
    const handoff = buildComponent2IntegrationFixture(component1);
    const result = validateComponent4CandidateHandoff(handoff, component1, false);

    expect(result).toEqual(["P1", "P2", "P3"]);
  });

  it("blocks the development fixture in production", () => {
    const component1 = recommendation(["P1", "P2"]);

    expect(() =>
      validateComponent4CandidateHandoff(
        buildComponent2IntegrationFixture(component1),
        component1,
        true,
      ),
    ).toThrow(Component2HandoffError);
    expect(
      getComponent2HandoffReadiness("component1-top10-fixture", true),
    ).toMatchObject({
      ready: false,
      real_component2: false,
      production_safe: false,
    });
  });

  it("rejects a future Component 2 handoff that changes identity or candidates", () => {
    const component1 = recommendation(["P1", "P2"]);
    const invalid: Component4CandidateHandoff = {
      source: "component2",
      request_id: component1.request_id,
      user_id: component1.user_id,
      component_version: "component2-v1",
      model_version: "context-v1",
      provider_ids: ["P1", "P-NOT-FROM-C1"],
    };

    expect(() =>
      validateComponent4CandidateHandoff(invalid, component1, true),
    ).toThrow("outside Component 1 Top-20");
  });

  it("keeps reserved Component 2 API mode fail-closed until the adapter exists", () => {
    expect(getComponent2HandoffReadiness("component2-api", true)).toMatchObject({
      ready: false,
      real_component2: false,
      production_safe: false,
    });
    expect(getComponent2HandoffReadiness("unexpected", false).ready).toBe(false);
  });
});
