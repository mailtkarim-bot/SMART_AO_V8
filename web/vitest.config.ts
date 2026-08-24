import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    globals: true,
    // Keep component tests reliable on shared/CPU-constrained runners.
    testTimeout: 15_000,
    hookTimeout: 15_000,
  },
});
