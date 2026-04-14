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

  it("loads recent foods through the existing service path", async () => {
    const hass = {
      callApi: vi.fn().mockResolvedValue({
        service_response: {
          profile_id: "profile-1",
          foods: [
            {
              food_id: "food-1",
              name: "Gouda jung",
              brand: "ja!",
              kcal_per_100g: 356,
            },
          ],
        },
      }),
    };

    const response = await BrizelCardUtils.getRecentFoods(hass, {
      profileId: "profile-1",
      limit: 4,
    });

    expect(hass.callApi).toHaveBeenCalledWith(
      "POST",
      "services/brizel_health/get_recent_foods?return_response",
      {
        profile_id: "profile-1",
        limit: 4,
      }
    );
    expect(response.profileId).toBe("profile-1");
    expect(response.foods[0].name).toBe("Gouda jung");
  });

  it("looks up a food by barcode through the shared service envelope", async () => {
    const hass = {
      callApi: vi.fn().mockResolvedValue({
        service_response: {
          status: "success",
          results: [
            {
              source_name: "open_food_facts",
              source_id: "3017624010701",
              name: "Nutella",
            },
          ],
          source_results: [],
        },
      }),
    };

    const response = await BrizelCardUtils.lookupExternalFoodByBarcode(hass, {
      barcode: "3017624010701",
    });

    expect(hass.callApi).toHaveBeenCalledWith(
      "POST",
      "services/brizel_health/lookup_external_food_by_barcode?return_response",
      {
        barcode: "3017624010701",
      }
    );
    expect(response.status).toBe("success");
    expect(response.results[0].source_name).toBe("open_food_facts");
  });

  it("creates a direct catalog food entry with meal type metadata", async () => {
    const hass = {
      callApi: vi.fn().mockResolvedValue({
        service_response: {
          profile_id: "profile-1",
          food_entry: {
            food_entry_id: "entry-1",
            profile_id: "profile-1",
            food_name: "Apple",
          },
        },
      }),
    };

    const response = await BrizelCardUtils.createFoodEntry(
      hass,
      { profile_id: "profile-1" },
      {
        foodId: "food-1",
        grams: 180,
        mealType: "dinner",
        source: "manual",
      }
    );

    expect(hass.callApi).toHaveBeenCalledWith(
      "POST",
      "services/brizel_health/create_food_entry?return_response",
      {
        profile_id: "profile-1",
        food_id: "food-1",
        grams: 180,
        meal_type: "dinner",
        source: "manual",
      }
    );
    expect(response.profile_id).toBe("profile-1");
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
