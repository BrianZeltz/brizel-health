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
    await flushPromises();

    card.shadowRoot.querySelector(".result-item").click();
    await flushPromises();

    expect(card.shadowRoot.querySelector(".detail-view")).not.toBeNull();
    expect(card.shadowRoot.querySelector(".detail-name").textContent).toContain("Gouda");
    expect(card.shadowRoot.textContent).toContain("Add to today");
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
    await flushPromises();

    expect(card.shadowRoot.textContent).toContain("No matching foods found");
  });

  it("can start a search from a recent food entry", async () => {
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
            },
          ],
        },
      }),
      "services/brizel_health/search_external_foods?return_response": (data) => ({
        service_response: {
          status: "success",
          results: [
            {
              source_name: "open_food_facts",
              source_id: "off-milch",
              name: data.query,
              brand: "Milbona",
              kcal_per_100g: 46,
            },
          ],
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

    card.shadowRoot.querySelector("[data-action='use-recent']").click();
    await flushPromises();

    expect(card.shadowRoot.querySelector("[data-role='search-input']").value).toContain(
      "Milch"
    );
    expect(card.shadowRoot.textContent).toContain("Milch 1,5%");
  });
});
