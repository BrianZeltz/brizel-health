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

  it("loads body measurement types through the shared service envelope", async () => {
    const hass = {
      callApi: vi.fn().mockResolvedValue({
        service_response: {
          measurement_types: [
            {
              key: "weight",
              display_unit: "lb",
            },
            {
              key: "waist",
              display_unit: "in",
            },
          ],
        },
      }),
    };

    const response = await BrizelCardUtils.getBodyMeasurementTypes(hass, {
      profileId: "profile-1",
    });

    expect(hass.callApi).toHaveBeenCalledWith(
      "POST",
      "services/brizel_health/get_body_measurement_types?return_response",
      {
        profile_id: "profile-1",
      }
    );
    expect(response[0].key).toBe("weight");
    expect(response[0].display_unit).toBe("lb");
  });

  it("loads body goal and progress summary through the shared service paths", async () => {
    const hass = {
      callApi: vi
        .fn()
        .mockResolvedValueOnce({
          service_response: {
            goal: {
              profile_id: "profile-1",
              target_weight_kg: 75,
              display_value: 165.35,
              display_unit: "lb",
            },
          },
        })
        .mockResolvedValueOnce({
          service_response: {
            summary: {
              measurement_type: "weight",
              latest_value: 180,
              display_unit: "lb",
              distance_to_goal_display: 14.65,
            },
          },
        }),
    };

    const goal = await BrizelCardUtils.getBodyGoal(hass, {
      profileId: "profile-1",
    });
    const summary = await BrizelCardUtils.getBodyProgressSummary(hass, {
      profileId: "profile-1",
    });

    expect(goal.display_unit).toBe("lb");
    expect(summary.display_unit).toBe("lb");
    expect(hass.callApi).toHaveBeenNthCalledWith(
      1,
      "POST",
      "services/brizel_health/get_body_goal?return_response",
      {
        profile_id: "profile-1",
      }
    );
    expect(hass.callApi).toHaveBeenNthCalledWith(
      2,
      "POST",
      "services/brizel_health/get_body_progress_summary?return_response",
      {
        profile_id: "profile-1",
        measurement_type: "weight",
      }
    );
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

  it("detects German automatically from Home Assistant language hints", () => {
    expect(
      BrizelCardUtils.resolveEffectiveUiLanguage({
        hass: { language: "de-DE" },
        preferredLanguage: "auto",
      })
    ).toBe("de");
  });

  it("keeps a manual language override above Home Assistant hints", () => {
    expect(
      BrizelCardUtils.resolveEffectiveUiLanguage({
        hass: { language: "en-US" },
        preferredLanguage: "de",
      })
    ).toBe("de");
    expect(
      BrizelCardUtils.translateText(
        {
          hass: { language: "en-US" },
          preferredLanguage: "de",
        },
        "logger.searchTitle"
      )
    ).toBe("Lebensmittel suchen");
  });

  it("uses real German UI text with umlauts and localized macro guidance", () => {
    expect(
      BrizelCardUtils.translateText(
        {
          hass: { language: "de-DE" },
          preferredLanguage: "auto",
        },
        "common.back"
      )
    ).toBe("Zurück");

    const macroData = BrizelCardUtils.getMacroDataFromOverview(
      {
        protein: {
          status: "within",
          consumed: 132,
          target_min: 120,
          target_recommended: 140,
          target_max: 140,
          remaining_to_min: 0,
          remaining_to_max: 8,
          over_amount: 0,
          display_text: "You are in range, 8 g protein left",
        },
      },
      "protein",
      {
        hass: { language: "de-DE" },
        preferredLanguage: "auto",
      }
    );

    expect(macroData.title).toBe("Protein");
    expect(macroData.displayText).toBe(
      "Im Zielbereich, noch 8 g Protein bis zum oberen Zielwert"
    );
  });

  it("sends explicit auto-clearing values for region and units when saving profile settings", async () => {
    const hass = {
      callApi: vi.fn().mockResolvedValue({
        service_response: {
          profile: {
            profile_id: "profile-1",
            display_name: "Brian",
            preferred_language: "auto",
            preferred_region: null,
            preferred_units: null,
          },
        },
      }),
    };

    await BrizelCardUtils.updateProfile(hass, {
      profileId: "profile-1",
      displayName: "Brian",
      preferredLanguage: "auto",
      preferredRegion: "",
      preferredUnits: "",
    });

    expect(hass.callApi).toHaveBeenCalledWith(
      "POST",
      "services/brizel_health/update_profile?return_response",
      {
        profile_id: "profile-1",
        display_name: "Brian",
        preferred_language: "auto",
        preferred_region: "",
        preferred_units: "",
      }
    );
  });

  it("formats entry source labels through the shared translation layer", () => {
    expect(
      BrizelCardUtils.getEntrySourceLabel("manual", {
        hass: { language: "de-DE" },
        preferredLanguage: "auto",
      })
    ).toBe("Manuell");
    expect(
      BrizelCardUtils.getEntrySourceLabel("barcode", {
        hass: { language: "en-US" },
        preferredLanguage: "auto",
      })
    ).toBe("Barcode");
  });

  it("formats body measurement labels through the shared translation layer", () => {
    expect(
      BrizelCardUtils.getBodyMeasurementTypeLabel("waist", {
        hass: { language: "de-DE" },
        preferredLanguage: "auto",
      })
    ).toBe("Taille");
    expect(
      BrizelCardUtils.getBodyMeasurementSourceLabel("manual", {
        hass: { language: "en-US" },
        preferredLanguage: "auto",
      })
    ).toBe("Manual");
  });

  it("filters weight out of body-measurement input options without removing it from the registry", () => {
    const options = BrizelCardUtils.getBodyMeasurementTypeOptions(
      [
        { key: "weight", display_unit: "lb" },
        { key: "waist", display_unit: "in" },
      ],
      {
        hass: { language: "en-US" },
        preferredLanguage: "auto",
      },
      { includeWeight: false }
    );

    expect(options).toEqual([
      expect.objectContaining({
        key: "waist",
        value: "waist",
        display_unit: "in",
        label: "Waist",
      }),
    ]);
  });

  it("extracts readable messages from nested service errors", () => {
    expect(
      BrizelCardUtils.getReadableErrorMessage({
        message: {
          detail: "Readable nested message",
        },
      })
    ).toBe("Readable nested message");

    expect(
      BrizelCardUtils.getReadableErrorMessage(
        {
          body: {
            message: "Readable body message",
          },
          error: {
            detail: "Readable error detail",
          },
        },
        "Fallback message"
      )
    ).toBe("Readable error detail");

    expect(
      BrizelCardUtils.getReadableErrorMessage(
        {
          body: {
            message: "Readable body message",
          },
        },
        "Fallback message"
      )
    ).toBe("Readable body message");
  });

  it("removes water through the shared hydration service path", async () => {
    const hass = {
      callApi: vi.fn().mockResolvedValue({
        service_response: {
          food_entry: {
            food_entry_id: "entry-water-1",
            profile_id: "profile-1",
            grams: 250,
          },
        },
      }),
    };

    const response = await BrizelCardUtils.removeWater(hass, {
      profileId: "profile-1",
      amountMl: 250,
    });

    expect(hass.callApi).toHaveBeenCalledWith(
      "POST",
      "services/brizel_health/remove_water?return_response",
      {
        profile_id: "profile-1",
        amount_ml: 250,
      }
    );
    expect(response.food_entry.profile_id).toBe("profile-1");
  });
});
