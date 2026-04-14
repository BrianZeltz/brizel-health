import { afterEach, beforeEach, vi } from "vitest";

if (!customElements.get("ha-icon")) {
  customElements.define("ha-icon", class extends HTMLElement {});
}

if (!window.matchMedia) {
  window.matchMedia = () => ({
    matches: false,
    media: "",
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent() {
      return false;
    },
  });
}

beforeEach(() => {
  document.body.innerHTML = "";
  window.customCards = [];
});

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
  document.body.innerHTML = "";
});
