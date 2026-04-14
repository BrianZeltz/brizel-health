import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["tests/frontend/setup.js"],
    include: ["tests/frontend/**/*.test.js"],
    restoreMocks: true,
    clearMocks: true,
  },
});
