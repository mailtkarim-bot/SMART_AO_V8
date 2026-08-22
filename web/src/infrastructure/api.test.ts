import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "./api";

describe("api client response parsing", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("maps a non-JSON error response to the generic status message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>proxy failure</html>", {
          status: 502,
          headers: { "Content-Type": "text/html" },
        }),
      ),
    );

    await expect(
      createApiClient("https://app.example.test", "token").listAssignedCases(),
    ).rejects.toThrow("La requête a échoué (502).");
  });
});
