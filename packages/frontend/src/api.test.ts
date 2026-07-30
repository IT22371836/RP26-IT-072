import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";


describe("Component 4 API client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("posts the strict Top-10 to Top-5 ranking contract with authentication", async () => {
    const providerIds = Array.from({ length: 10 }, (_, index) => `P${index + 1}`);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          component_version: "component4-phase6",
          request_id: "RTEST1",
          run_id: "C4RUN-TEST",
          user_id: "UTEST1",
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

    await api.rankComponent4("RTEST1", providerIds, "test-token");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/component4/rank");
    expect(options?.method).toBe("POST");
    expect(options?.headers).toMatchObject({
      Authorization: "Bearer test-token",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(String(options?.body))).toEqual({
      request_id: "RTEST1",
      provider_ids: providerIds,
      top_k: 5,
      force_recalculate: false,
    });
  });
});
