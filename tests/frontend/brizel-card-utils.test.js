import { describe, expect, it, vi } from "vitest";

import { BrizelCardUtils } from "../../custom_components/brizel_health/frontend/brizel-card-utils.js";

describe("BrizelCardUtils", () => {
  it("prefers explicit profile overrides", () => {
    expect(
      BrizelCardUtils.getConfiguredProfile({
        profile: "brian",
        profile_id: "ignored",
      })
    ).toBe("brian");
    expect(
      BrizelCardUtils.getConfiguredProfile({
        profile_id: "brian",
      })
    ).toBe("brian");
  });

  it("normalizes service envelopes from Home Assistant responses", async () => {
    const hass = {
      callApi: vi.fn().mockResolvedValue({
        service_response: {
          status: "success",
          results: [
            {
              source_name: "bls",
              source_id: "BLS123",
              name: "Gouda",
            },
          ],
          source_results: [],
        },
      }),
    };

    const response = await BrizelCardUtils.searchExternalFoods(hass, {
      query: "gouda",
      profileId: "profile-1",
    });

    expect(hass.callApi).toHaveBeenCalledWith(
      "POST",
      "services/brizel_health/search_external_foods?return_response",
      {
        query: "gouda",
        limit: 10,
        profile_id: "profile-1",
      }
    );
    expect(response.status).toBe("success");
    expect(response.results[0].source_name).toBe("bls");
  });

  it("builds human profile errors for missing links", () => {
    const error = BrizelCardUtils.normalizeServiceError(
      new Error("No Brizel Health profile is linked to the active Home Assistant user."),
      {}
    );

    expect(error.kind).toBe("no_link");
    expect(error.title).toBe("No Brizel profile linked");
  });
});
