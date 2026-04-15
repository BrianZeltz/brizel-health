import { beforeEach, describe, expect, it, vi } from "vitest";

import "../../custom_components/brizel_health/frontend/brizel-health-app-card.js";

const CardClass = customElements.get("brizel-health-app-card");

const flushPromises = async () => {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
};

const clickElement = (element) => {
  element.dispatchEvent(
    new MouseEvent("click", {
      bubbles: true,
      composed: true,
    })
  );
};

const createHass = (handlers = {}, options = {}) => ({
  user: { id: "ha-user-1" },
  language: options.language ?? "en-US",
  callApi: vi.fn(async (_method, path, data) => {
    const handler = handlers[path];
    if (!handler) {
      throw new Error(`Unhandled callApi path: ${path}`);
    }
    return typeof handler === "function" ? handler(data) : handler;
  }),
});

const overviewResponse = (overrides = {}) => ({
  service_response: {
    profile_id: "profile-1",
    profile_display_name: "Brian",
    overview: {
      has_data: false,
      ...overrides,
    },
  },
});

describe("brizel-health-app-card", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = "";
  });

  it("renders the home shell in German from Home Assistant auto language", async () => {
    const hass = createHass(
      {
        "services/brizel_health/get_daily_overview?return_response": () =>
          overviewResponse(),
      },
      { language: "de-DE" }
    );

    const card = new CardClass();
    card.setConfig({});
    card.hass = hass;
    document.body.append(card);

    await flushPromises();

    expect(card.shadowRoot.textContent).toContain("Brizel Start");
    expect(card.shadowRoot.textContent).toContain("Schnellaktionen");
    expect(card.shadowRoot.textContent).toContain("Ernährung");
    expect(card.shadowRoot.textContent).toContain("Wasser entfernen");
  });

  it("opens the embedded logger dialog from the quick add action", async () => {
    const hass = createHass({
      "services/brizel_health/get_daily_overview?return_response": () =>
        overviewResponse(),
      "services/brizel_health/get_recent_foods?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          foods: [],
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({});
    card.hass = hass;
    document.body.append(card);

    await flushPromises();

    clickElement(card.shadowRoot.querySelector("[data-action='quick-add-food']"));
    vi.runAllTimers();
    await flushPromises();

    const loggerCard = card.shadowRoot.querySelector("brizel-food-logger-card");
    expect(loggerCard).not.toBeNull();
    expect(loggerCard.shadowRoot.querySelector(".dialog-layer")).not.toBeNull();
    expect(loggerCard.shadowRoot.querySelector("[data-role='search-input']")).not.toBeNull();
  });

  it("opens the embedded logger in barcode mode from the home quick action", async () => {
    const hass = createHass({
      "services/brizel_health/get_daily_overview?return_response": () =>
        overviewResponse(),
      "services/brizel_health/get_recent_foods?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          foods: [],
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({});
    card.hass = hass;
    document.body.append(card);

    await flushPromises();

    clickElement(card.shadowRoot.querySelector("[data-action='quick-barcode']"));
    vi.runAllTimers();
    await flushPromises();

    const loggerCard = card.shadowRoot.querySelector("brizel-food-logger-card");
    expect(loggerCard).not.toBeNull();
    expect(loggerCard.shadowRoot.querySelector(".dialog-layer")).not.toBeNull();
    expect(loggerCard.shadowRoot.querySelector("[data-role='barcode-input']")).not.toBeNull();
  });

  it("loads profile settings and uses the saved profile language override", async () => {
    const hass = createHass(
      {
        "services/brizel_health/get_daily_overview?return_response": () =>
          overviewResponse(),
        "services/brizel_health/get_profile?return_response": () => ({
          service_response: {
            profile: {
              profile_id: "profile-1",
              display_name: "Brian",
              linked_ha_user_id: "ha-user-1",
              preferred_language: "de",
              preferred_region: "germany",
              preferred_units: "metric",
            },
          },
        }),
        "services/brizel_health/get_body_profile?return_response": () => ({
          service_response: {
            body_profile: {
              profile_id: "profile-1",
              age_years: 34,
              sex: "male",
              height_cm: 180,
              weight_kg: 82,
              activity_level: "moderate",
            },
          },
        }),
        "services/brizel_health/get_body_targets?return_response": () => ({
          service_response: {
            targets: {
              target_daily_kcal: 2400,
              target_daily_protein: 140,
              target_daily_fat: 80,
              missing_fields: [],
              unsupported_reasons: [],
            },
          },
        }),
      },
      { language: "en-US" }
    );

    const card = new CardClass();
    card.setConfig({ initial_section: "settings" });
    card.hass = hass;
    document.body.append(card);

    await flushPromises();
    await flushPromises();

    expect(card.shadowRoot.textContent).toContain("Profil & Einstellungen");
    expect(card.shadowRoot.textContent).toContain("Anzeigename");
    expect(card.shadowRoot.textContent).toContain("Deutschland");
  });

  it("renders history entries and reuses them through the logger flow", async () => {
    const hass = createHass({
      "services/brizel_health/get_daily_overview?return_response": () =>
        overviewResponse(),
      "services/brizel_health/get_food_entries_for_profile_date?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          food_entries: [
            {
              food_entry_id: "entry-1",
              food_id: "food-1",
              food_name: "Apple",
              food_brand: null,
              grams: 180,
              kcal: 94,
              source: "manual",
              meal_type: "snack",
              consumed_at: "2026-04-15T08:45:00+02:00",
            },
          ],
        },
      }),
      "services/brizel_health/get_food?return_response": () => ({
        service_response: {
          food: {
            food_id: "food-1",
            name: "Apple",
            brand: null,
            kcal_per_100g: 52,
            protein_per_100g: 0.3,
            carbs_per_100g: 14,
            fat_per_100g: 0.2,
          },
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({ initial_section: "history" });
    card.hass = hass;
    document.body.append(card);

    await flushPromises();
    await flushPromises();

    expect(card.shadowRoot.textContent).toContain("Apple");

    clickElement(card.shadowRoot.querySelector("[data-action='reuse-entry']"));
    vi.runAllTimers();
    await flushPromises();
    await flushPromises();

    const loggerCard = card.shadowRoot.querySelector("brizel-food-logger-card");
    expect(loggerCard).not.toBeNull();
    expect(loggerCard.shadowRoot.querySelector(".detail-view")).not.toBeNull();
    expect(loggerCard.shadowRoot.querySelector(".detail-name").textContent).toContain("Apple");
    expect(loggerCard.shadowRoot.querySelector("[data-role='amount-input']").value).toBe("180");
  });

  it("wires the remove-water quick action to the shared hydration service", async () => {
    const hass = createHass({
      "services/brizel_health/get_daily_overview?return_response": () =>
        overviewResponse(),
      "services/brizel_health/remove_water?return_response": () => ({
        service_response: {
          food_entry: {
            food_entry_id: "entry-water-1",
            profile_id: "profile-1",
            food_name: "Water",
            grams: 250,
          },
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({ initial_section: "hydration" });
    card.hass = hass;
    document.body.append(card);

    await flushPromises();

    clickElement(card.shadowRoot.querySelector("[data-action='quick-remove-water']"));
    await flushPromises();

    expect(hass.callApi).toHaveBeenCalledWith(
      "POST",
      "services/brizel_health/remove_water?return_response",
      {
        profile_id: "profile-1",
        amount_ml: 250,
      }
    );
    expect(card.shadowRoot.textContent).toContain("Removed 250 ml water from today.");
  });
});
