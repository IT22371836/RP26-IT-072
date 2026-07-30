import type {
  Component4CandidateHandoff,
  RecommendationResponse,
} from "./types";

export const COMPONENT2_HANDOFF_MODE =
  import.meta.env.VITE_COMPONENT2_HANDOFF_MODE ?? "component1-top10-fixture";

export interface Component2HandoffReadiness {
  mode: string;
  ready: boolean;
  real_component2: boolean;
  production_safe: boolean;
  detail: string;
}

export class Component2HandoffError extends Error {}

export function getComponent2HandoffReadiness(
  mode: string,
  isProduction: boolean,
): Component2HandoffReadiness {
  if (mode === "component1-top10-fixture") {
    return {
      mode,
      ready: !isProduction,
      real_component2: false,
      production_safe: false,
      detail: isProduction
        ? "Component 2 is not connected. The development Top-10 fixture is disabled in production."
        : "Development-only Component 1 Top-10 fixture is active.",
    };
  }
  if (mode === "component2-api") {
    return {
      mode,
      ready: false,
      real_component2: false,
      production_safe: false,
      detail: "Component 2 API mode is reserved but its real Top-10 adapter is not connected.",
    };
  }
  return {
    mode,
    ready: false,
    real_component2: false,
    production_safe: false,
    detail: `Unsupported Component 2 handoff mode: ${mode}`,
  };
}

export const COMPONENT2_HANDOFF_READINESS = getComponent2HandoffReadiness(
  COMPONENT2_HANDOFF_MODE,
  import.meta.env.PROD,
);

export function buildComponent2IntegrationFixture(
  recommendations: RecommendationResponse,
): Component4CandidateHandoff {
  return {
    source: "development_fixture",
    request_id: recommendations.request_id,
    user_id: recommendations.user_id,
    component_version: "not-component2",
    model_version: "not-component2",
    provider_ids: Array.from(
      new Set(recommendations.results.map((provider) => provider.provider_id)),
    ).slice(0, 10),
  };
}

export function validateComponent4CandidateHandoff(
  handoff: Component4CandidateHandoff,
  recommendations: RecommendationResponse,
  isProduction: boolean,
): string[] {
  if (handoff.source === "development_fixture" && isProduction) {
    throw new Component2HandoffError(
      "The Component 2 development fixture cannot be used in production.",
    );
  }
  if (handoff.request_id !== recommendations.request_id) {
    throw new Component2HandoffError("The handoff changed request_id.");
  }
  if (handoff.user_id !== recommendations.user_id) {
    throw new Component2HandoffError("The handoff changed user_id.");
  }
  if (!handoff.component_version.trim() || !handoff.model_version.trim()) {
    throw new Component2HandoffError("The handoff must include component and model versions.");
  }
  if (handoff.provider_ids.length < 1 || handoff.provider_ids.length > 10) {
    throw new Component2HandoffError("The handoff must contain between one and ten providers.");
  }
  if (new Set(handoff.provider_ids).size !== handoff.provider_ids.length) {
    throw new Component2HandoffError("The handoff provider IDs must be unique.");
  }
  const component1ProviderIds = new Set(
    recommendations.results.map((provider) => provider.provider_id),
  );
  if (handoff.provider_ids.some((providerId) => !component1ProviderIds.has(providerId))) {
    throw new Component2HandoffError(
      "The handoff introduced a provider outside Component 1 Top-20.",
    );
  }
  return [...handoff.provider_ids];
}
