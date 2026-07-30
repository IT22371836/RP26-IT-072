import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("authentication entry flow", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("shows sign in by default and allows switching to registration", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(screen.getByRole("heading", { name: "Create your account" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /I need a service/ })).toBeInTheDocument();
  });

  it("renders the explicit Top-10 fixture handoff and real Component 4 Top-5", async () => {
    const user = {
      user_id: "UTEST1",
      email: "customer@example.com",
      full_name: "Test Customer",
      role: "customer",
      is_active: true,
      created_at: "2026-07-30T10:00:00Z",
    };
    const component1Providers = Array.from({ length: 20 }, (_, index) => ({
      provider_id: `P${String(index + 1).padStart(5, "0")}`,
      provider_name: `Relevant Provider ${index + 1}`,
      category: "Electricians",
      district: "Colombo",
      city: "Kottawa",
      skills: "wiring",
      description: "Relevant electrical service provider.",
      experience_years: 5,
      rating: 4.5,
      review_count: 20,
      booking_success_rate: 0.9,
      interaction_count: 15,
      hybrid_score: 0.9 - index / 100,
      tfidf_score: 0.8,
      bert_score: 0.85,
      cf_score: 0.75,
    }));
    const selectedInteractions: Array<Record<string, unknown>> = [];
    localStorage.setItem(
      "weda-session",
      JSON.stringify({ token: "test-token", user }),
    );
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      async (input, options) => {
        const path = new URL(String(input)).pathname;
        const method = options?.method ?? "GET";
        let body: unknown;
        if (path.endsWith("/auth/me")) {
          body = user;
        } else if (path.endsWith("/customers/me")) {
          body = {
            customer_id: "CTEST1",
            user_id: user.user_id,
            phone: "+94770000000",
            district: "Colombo",
            city: "Kottawa",
            preferred_language: "English",
            created_at: "2026-07-30T10:00:00Z",
            updated_at: "2026-07-30T10:00:00Z",
          };
        } else if (path.endsWith("/service-requests/me")) {
          body = [];
        } else if (path.endsWith("/interactions/me")) {
          body = selectedInteractions;
        } else if (path.endsWith("/service-requests") && method === "POST") {
          body = {
            request_id: "RTEST1",
            user_id: user.user_id,
            request_text: "Need an electrician for damaged sockets",
            category: "Electricians",
            district: "Colombo",
            city: "Kottawa",
            urgency: "normal",
            created_at: "2026-07-30T10:00:00Z",
          };
        } else if (path.endsWith("/component1/recommend")) {
          body = {
            component_version: "1.0.0",
            model_version: "component1-test",
            request_id: "RTEST1",
            query: "Need an electrician for damaged sockets",
            user_id: user.user_id,
            results: component1Providers,
          };
        } else if (path.endsWith("/component4/rank")) {
          body = {
            component_version: "component4-phase6",
            request_id: "RTEST1",
            run_id: "C4RUN-TEST1",
            user_id: user.user_id,
            input_count: 10,
            output_count: 5,
            requested_top_k: 5,
            candidate_provider_ids: component1Providers.slice(0, 10).map(
              (provider) => provider.provider_id,
            ),
            providers: component1Providers.slice(0, 5).map((provider, index) => ({
              provider_id: provider.provider_id,
              provider_name: `Trust Provider ${index + 1}`,
              category: provider.category,
              district: provider.district,
              city: provider.city,
              rank: index + 1,
              final_score: 0.55 - index / 100,
              aspect_scores: {
                quality: 0.8,
                punctuality: 0.5,
                communication: 0.6,
                professionalism: 0.7,
              },
              mean_credibility: 0.9,
              review_count: 8,
              effective_review_count: 7.2,
              reliability_factor: 0.26,
              evidence_status: "limited",
              score_source: "catf_evidence",
              platform_rating: 4.6,
              platform_review_count: 45,
            })),
            versions: {
              catf_version: "catf-v1",
              weight_version: "category-weights-v1",
              category_prior_version: "category-priors-v1",
              absa_model_version: "absa-v1",
              credibility_model_version: "credibility-v1",
            },
            cached: false,
            processing_time_ms: 3,
          };
        } else if (path.endsWith("/interactions") && method === "POST") {
          const payload = JSON.parse(String(options?.body));
          const interaction = {
            ...payload,
            interaction_id: "ITEST1",
            user_id: user.user_id,
            rating: null,
            timestamp: "2026-07-30T10:01:00Z",
          };
          selectedInteractions.push(interaction);
          body = interaction;
        } else {
          return new Response(JSON.stringify({ detail: `Unhandled test route: ${path}` }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    );

    render(<App />);
    expect(
      await screen.findByRole("heading", { name: "What needs fixing today?" }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Describe the work"), {
      target: { value: "Need an electrician for damaged sockets" },
    });
    fireEvent.change(screen.getByLabelText("City"), {
      target: { value: "Kottawa" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Find my best matches/ }));

    expect(
      await screen.findByRole("heading", { name: "Your trust-aware final matches" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Component 2 integration fixture")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Select this provider" })).toHaveLength(5);
    const rankCall = fetchMock.mock.calls.find(([url]) =>
      new URL(String(url)).pathname.endsWith("/component4/rank"),
    );
    expect(rankCall).toBeDefined();
    expect(JSON.parse(String(rankCall?.[1]?.body)).provider_ids).toHaveLength(10);

    fireEvent.click(screen.getAllByRole("button", { name: "Select this provider" })[0]);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Selected" })).toBeDisabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Selected Providers" }));
    expect(await screen.findByText("Trust Provider 1")).toBeInTheDocument();
  });
});
