import { describe, expect, it } from "vitest";

import {
  DEFAULT_API_BASE_URL,
  assertRuntimeApiUrl,
  isLocalApiUrl,
  normalizeApiBaseUrl,
  resolveApiBaseUrl,
} from "./runtimeConfig";

describe("runtimeConfig", () => {
  it("normalizes a valid API base URL without a trailing slash", () => {
    expect(normalizeApiBaseUrl(" https://api.example.test/// ")).toBe("https://api.example.test");
  });

  it("rejects credentials, query strings and unsupported protocols", () => {
    expect(() => normalizeApiBaseUrl("https://user:secret@example.test")).toThrow(/identifiants/); // pragma: allowlist secret
    expect(() => normalizeApiBaseUrl("https://api.example.test?tenant=secret")).toThrow(/query/);
    expect(() => normalizeApiBaseUrl("ftp://api.example.test")).toThrow(/HTTP ou HTTPS/);
  });

  it("allows HTTP only for local development when the page is HTTPS", () => {
    expect(assertRuntimeApiUrl("http://localhost:8000/", "https:")).toBe("http://localhost:8000");
    expect(
      assertRuntimeApiUrl("https://app.example.test/api", "https:", "https://app.example.test"),
    ).toBe("https://app.example.test/api");
    expect(() =>
      assertRuntimeApiUrl("https://api.example.test", "https:", "https://app.example.test"),
    ).toThrow(/origine/);
    expect(isLocalApiUrl("http://127.0.0.1:8000")).toBe(true);
    expect(isLocalApiUrl("https://api.example.test")).toBe(false);
  });

  it("prefers the build-time URL and falls back to the page origin in HTTPS", () => {
    expect(
      resolveApiBaseUrl(
        "https://app.example.test/",
        "https:",
        "https://app.example.test",
      ),
    ).toBe("https://app.example.test");
    expect(resolveApiBaseUrl(undefined, "https:", "https://app.example.test")).toBe(
      "https://app.example.test",
    );
    expect(
      resolveApiBaseUrl("https://api.example.test", "https:", "https://app.example.test"),
    ).toBe("https://app.example.test");
    expect(resolveApiBaseUrl(undefined, "http:")).toBe(DEFAULT_API_BASE_URL);
  });
});
