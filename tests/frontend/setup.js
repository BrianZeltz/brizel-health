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

if (!window.requestAnimationFrame) {
  window.requestAnimationFrame = (callback) => window.setTimeout(callback, 0);
}

if (!window.cancelAnimationFrame) {
  window.cancelAnimationFrame = (handle) => window.clearTimeout(handle);
}

if (!window.confirm) {
  window.confirm = () => true;
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
