import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";


describe("Component 4 API client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("posts the strict Top-10 to Top-5 ranking contract with authentication", async () => {
    const providerIds = Array.from({ length: 10 }, (_, index) => `P${index + 1}`);
    const handoff = {
      source: "component2" as const,
      request_id: "RTEST1",
      user_id: "UTEST1",
      component_version: "component2-v1",
      model_version: "context-v1",
      provider_ids: providerIds,
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          component_version: "component4-phase6",
          request_id: "RTEST1",
          run_id: "C4RUN-TEST",
          user_id: "UTEST1",
          handoff,
          input_count: 10,
          output_count: 0,
          requested_top_k: 5,
          candidate_provider_ids: providerIds,
          providers: [],
          versions: {
            catf_version: "catf-v1",
            weight_version: "category-weights-v1",
            category_prior_version: "category-priors-v1",
            absa_model_version: "absa-v1",
            credibility_model_version: "credibility-v1",
          },
          cached: false,
          processing_time_ms: 1,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await api.rankComponent4(handoff, "test-token");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/component4/rank");
    expect(options?.method).toBe("POST");
    expect(options?.headers).toMatchObject({
      Authorization: "Bearer test-token",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(String(options?.body))).toEqual({
      ...handoff,
      top_k: 5,
      force_recalculate: false,
    });
  });

  it("fetches the public provider trust profile", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ provider_id: "P00001" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await api.getProviderTrustProfile("P00001", "test-token");

    const [url, options] = fetchMock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/providers/P00001/trust-profile");
    expect(options?.headers).toMatchObject({ Authorization: "Bearer test-token" });
  });

  it("submits a written review only through the completed-booking rating route", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ interaction_id: "IRATED1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await api.rateBooking("ICOMPLETE1", 5, " Excellent work. ", "test-token");

    const [url, options] = fetchMock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/interactions/ICOMPLETE1/rate");
    expect(options?.method).toBe("POST");
    expect(JSON.parse(String(options?.body))).toEqual({
      rating: 5,
      review_text: "Excellent work.",
    });
  });
});
