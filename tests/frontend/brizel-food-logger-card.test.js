import { beforeEach, describe, expect, it, vi } from "vitest";

import "../../custom_components/brizel_health/frontend/brizel-food-logger-card.js";

const CardClass = customElements.get("brizel-food-logger-card");

const flushPromises = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

const createHass = (handlers = {}) => ({
  user: { id: "ha-user-1" },
  callApi: vi.fn(async (_method, path, data) => {
    const handler = handlers[path];
    if (!handler) {
      throw new Error(`Unhandled callApi path: ${path}`);
    }
    return handler(data);
  }),
});

describe("brizel-food-logger-card", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = "";
  });

  it("opens the dialog when the action button is clicked", async () => {
    const card = new CardClass();
    card.setConfig({});
    card.hass = createHass();
    document.body.append(card);

    card.shadowRoot.querySelector("[data-action='open-dialog']").click();
    vi.runAllTimers();
    await flushPromises();

    expect(card.shadowRoot.querySelector(".dialog-layer")).not.toBeNull();
    expect(card.shadowRoot.querySelector("[data-role='search-input']")).not.toBeNull();
  });

  it("renders search results after typing without crashing the input flow", async () => {
    const hass = createHass({
      "services/brizel_health/get_recent_foods?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          foods: [],
        },
      }),
      "services/brizel_health/search_external_foods?return_response": () => ({
        service_response: {
          status: "success",
          results: [
            {
              source_name: "open_food_facts",
              source_id: "off-1",
              name: "Kinder Country",
              brand: "Kinder",
              kcal_per_100g: 560,
            },
          ],
          source_results: [],
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({ min_query_length: 2, debounce_ms: 200 });
    card.hass = hass;
    document.body.append(card);

    card.shadowRoot.querySelector("[data-action='open-dialog']").click();
    vi.runAllTimers();
    await flushPromises();

    const input = card.shadowRoot.querySelector("[data-role='search-input']");
    input.value = "ki";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));

    vi.advanceTimersByTime(220);
    vi.runAllTimers();
    await flushPromises();

    expect(hass.callApi).toHaveBeenCalled();
    expect(card.shadowRoot.querySelector(".results-list")).not.toBeNull();
    expect(card.shadowRoot.querySelector(".result-name").textContent).toContain(
      "Kinder Country"
    );
    expect(card.shadowRoot.querySelector("[data-role='search-input']").value).toBe("ki");
  });

  it("opens the detail step after clicking a result", async () => {
    const hass = createHass({
      "services/brizel_health/get_recent_foods?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          foods: [],
        },
      }),
      "services/brizel_health/search_external_foods?return_response": () => ({
        service_response: {
          status: "success",
          results: [
            {
              source_name: "bls",
              source_id: "BLS123",
              name: "Gouda",
              brand: null,
              kcal_per_100g: 356,
            },
          ],
          source_results: [],
        },
      }),
      "services/brizel_health/get_external_food_detail?return_response": () => ({
        service_response: {
          food_detail: {
            source_name: "bls",
            source_id: "BLS123",
            name: "Gouda",
            brand: null,
            kcal_per_100g: 356,
            protein_per_100g: 24,
            carbs_per_100g: 0.1,
            fat_per_100g: 28,
            basis_amount: 100,
            basis_unit: "g",
            allowed_units: ["g"],
            default_unit: "g",
            default_amount: 100,
          },
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({ min_query_length: 2, debounce_ms: 50 });
    card.hass = hass;
    document.body.append(card);

    card.shadowRoot.querySelector("[data-action='open-dialog']").click();
    vi.runAllTimers();
    await flushPromises();

    const input = card.shadowRoot.querySelector("[data-role='search-input']");
    input.value = "go";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));

    vi.advanceTimersByTime(60);
    vi.runAllTimers();
    await flushPromises();

    card.shadowRoot.querySelector(".result-item").click();
    await flushPromises();

    expect(card.shadowRoot.querySelector(".detail-view")).not.toBeNull();
    expect(card.shadowRoot.querySelector(".detail-name").textContent).toContain("Gouda");
    expect(card.shadowRoot.textContent).toContain("Add to today");
  });

  it("uses source-provided unit options with natural defaults", async () => {
    const hass = createHass({
      "services/brizel_health/get_recent_foods?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          foods: [],
        },
      }),
      "services/brizel_health/search_external_foods?return_response": () => ({
        service_response: {
          status: "success",
          results: [
            {
              source_name: "open_food_facts",
              source_id: "off-1",
              name: "Toast Cheese",
              brand: "Example Brand",
              kcal_per_100g: 310,
            },
          ],
          source_results: [],
        },
      }),
      "services/brizel_health/get_external_food_detail?return_response": () => ({
        service_response: {
          food_detail: {
            source_name: "open_food_facts",
            source_id: "off-1",
            name: "Toast Cheese",
            brand: "Example Brand",
            kcal_per_100g: 310,
            protein_per_100g: 18,
            carbs_per_100g: 2,
            fat_per_100g: 26,
            basis_amount: 100,
            basis_unit: "g",
            allowed_units: ["slice", "g"],
            default_unit: "slice",
            default_amount: 1,
            unit_options: [
              {
                unit: "slice",
                label: "slice",
                default_amount: 1,
                grams_per_unit: 25,
                description: "1 slice (25 g)",
              },
              {
                unit: "g",
                label: "g",
                default_amount: 100,
                grams_per_unit: 1,
                description: null,
              },
            ],
          },
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({ min_query_length: 2, debounce_ms: 50 });
    card.hass = hass;
    document.body.append(card);

    card.shadowRoot.querySelector("[data-action='open-dialog']").click();
    vi.runAllTimers();
    await flushPromises();

    const input = card.shadowRoot.querySelector("[data-role='search-input']");
    input.value = "to";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));

    vi.advanceTimersByTime(60);
    vi.runAllTimers();
    await flushPromises();

    card.shadowRoot.querySelector(".result-item").click();
    await flushPromises();

    expect(card.shadowRoot.querySelector("[data-role='amount-input']").value).toBe("1");
    expect(card.shadowRoot.textContent).toContain("1 slice (25 g)");

    const unitSelect = card.shadowRoot.querySelector("[data-role='unit-select']");
    unitSelect.value = "g";
    unitSelect.dispatchEvent(new Event("change", { bubbles: true, composed: true }));

    expect(card.shadowRoot.querySelector("[data-role='amount-input']").value).toBe("100");
  });

  it("shows recent foods when the search is empty", async () => {
    const hass = createHass({
      "services/brizel_health/get_recent_foods?return_response": () => ({
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
    });

    const card = new CardClass();
    card.setConfig({});
    card.hass = hass;
    document.body.append(card);

    card.shadowRoot.querySelector("[data-action='open-dialog']").click();
    vi.runAllTimers();
    await flushPromises();

    expect(card.shadowRoot.textContent).toContain("Recent foods");
    expect(card.shadowRoot.textContent).toContain("Gouda jung");
  });

  it("renders a no-results state when the search returns empty", async () => {
    const hass = createHass({
      "services/brizel_health/get_recent_foods?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          foods: [],
        },
      }),
      "services/brizel_health/search_external_foods?return_response": () => ({
        service_response: {
          status: "empty",
          results: [],
          source_results: [],
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({ min_query_length: 2, debounce_ms: 50 });
    card.hass = hass;
    document.body.append(card);

    card.shadowRoot.querySelector("[data-action='open-dialog']").click();
    vi.runAllTimers();
    await flushPromises();

    const input = card.shadowRoot.querySelector("[data-role='search-input']");
    input.value = "gr";
    input.dispatchEvent(new Event("input", { bubbles: true, composed: true }));

    vi.advanceTimersByTime(60);
    vi.runAllTimers();
    await flushPromises();

    expect(card.shadowRoot.textContent).toContain("No matching foods found");
  });

  it("opens a reusable detail view from a recent food entry", async () => {
    const hass = createHass({
      "services/brizel_health/get_recent_foods?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          foods: [
            {
              food_id: "food-1",
              name: "Milch 1,5%",
              brand: "Milbona",
              kcal_per_100g: 46,
              protein_per_100g: 3.4,
              carbs_per_100g: 4.9,
              fat_per_100g: 1.5,
              last_logged_grams: 200,
              last_meal_type: "breakfast",
            },
          ],
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({ min_query_length: 2, debounce_ms: 50 });
    card.hass = hass;
    document.body.append(card);

    card.shadowRoot.querySelector("[data-action='open-dialog']").click();
    vi.runAllTimers();
    await flushPromises();

    card.shadowRoot.querySelector("[data-action='reuse-recent']").click();
    await flushPromises();

    expect(card.shadowRoot.querySelector(".detail-view")).not.toBeNull();
    expect(card.shadowRoot.querySelector(".detail-name").textContent).toContain("Milch 1,5%");
    expect(card.shadowRoot.querySelector("[data-role='amount-input']").value).toBe("200");
    expect(card.shadowRoot.querySelector("[data-role='meal-type-select']").value).toBe(
      "breakfast"
    );
  });

  it("supports the barcode flow and opens detail when a product is found", async () => {
    const hass = createHass({
      "services/brizel_health/get_recent_foods?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          foods: [],
        },
      }),
      "services/brizel_health/lookup_external_food_by_barcode?return_response": () => ({
        service_response: {
          status: "success",
          results: [
            {
              source_name: "open_food_facts",
              source_id: "3017624010701",
              name: "Nutella",
              brand: "Ferrero",
              kcal_per_100g: 539,
            },
          ],
          source_results: [],
        },
      }),
      "services/brizel_health/get_external_food_detail?return_response": () => ({
        service_response: {
          food_detail: {
            source_name: "open_food_facts",
            source_id: "3017624010701",
            name: "Nutella",
            brand: "Ferrero",
            kcal_per_100g: 539,
            protein_per_100g: 6.3,
            carbs_per_100g: 57.5,
            fat_per_100g: 30.9,
            basis_amount: 100,
            basis_unit: "g",
            allowed_units: ["g"],
            default_unit: "g",
            default_amount: 30,
          },
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({});
    card.hass = hass;
    document.body.append(card);

    card.shadowRoot.querySelector("[data-action='open-dialog']").click();
    vi.runAllTimers();
    await flushPromises();

    card.shadowRoot.querySelector("[data-action='set-entry-mode'][data-mode='barcode']").click();
    const barcodeInput = card.shadowRoot.querySelector("[data-role='barcode-input']");
    barcodeInput.value = "3017624010701";
    barcodeInput.dispatchEvent(new Event("input", { bubbles: true, composed: true }));

    card.shadowRoot.querySelector("[data-action='lookup-barcode']").click();
    await flushPromises();
    await flushPromises();

    expect(card.shadowRoot.querySelector(".detail-view")).not.toBeNull();
    expect(card.shadowRoot.textContent).toContain("Nutella");
  });

  it("shows a clear empty state when no barcode match is found", async () => {
    const hass = createHass({
      "services/brizel_health/get_recent_foods?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          foods: [],
        },
      }),
      "services/brizel_health/lookup_external_food_by_barcode?return_response": () => ({
        service_response: {
          status: "empty",
          results: [],
          source_results: [],
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({});
    card.hass = hass;
    document.body.append(card);

    card.shadowRoot.querySelector("[data-action='open-dialog']").click();
    vi.runAllTimers();
    await flushPromises();

    card.shadowRoot.querySelector("[data-action='set-entry-mode'][data-mode='barcode']").click();
    const barcodeInput = card.shadowRoot.querySelector("[data-role='barcode-input']");
    barcodeInput.value = "12345678";
    barcodeInput.dispatchEvent(new Event("input", { bubbles: true, composed: true }));

    card.shadowRoot.querySelector("[data-action='lookup-barcode']").click();
    await flushPromises();

    expect(card.shadowRoot.textContent).toContain("No product found for this barcode");
  });

  it("saves a reused recent food with the selected meal type", async () => {
    const hass = createHass({
      "services/brizel_health/get_recent_foods?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          foods: [
            {
              food_id: "food-1",
              name: "Apple",
              brand: null,
              kcal_per_100g: 52,
              protein_per_100g: 0.3,
              carbs_per_100g: 14,
              fat_per_100g: 0.2,
              last_logged_grams: 180,
            },
          ],
        },
      }),
      "services/brizel_health/create_food_entry?return_response": () => ({
        service_response: {
          profile_id: "profile-1",
          food_entry: {
            food_entry_id: "entry-1",
            profile_id: "profile-1",
            food_name: "Apple",
          },
        },
      }),
    });

    const card = new CardClass();
    card.setConfig({});
    card.hass = hass;
    document.body.append(card);

    card.shadowRoot.querySelector("[data-action='open-dialog']").click();
    vi.runAllTimers();
    await flushPromises();

    card.shadowRoot.querySelector("[data-action='reuse-recent']").click();
    await flushPromises();

    const mealSelect = card.shadowRoot.querySelector("[data-role='meal-type-select']");
    mealSelect.value = "dinner";
    mealSelect.dispatchEvent(new Event("change", { bubbles: true, composed: true }));

    card.shadowRoot.querySelector("[data-action='submit-log']").click();
    await flushPromises();

    expect(hass.callApi).toHaveBeenCalledWith(
      "POST",
      "services/brizel_health/create_food_entry?return_response",
      {
        food_id: "food-1",
        grams: 180,
        meal_type: "dinner",
        source: "manual",
      }
    );
  });
});
