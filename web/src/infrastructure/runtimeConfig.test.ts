import { describe, expect, it } from "vitest";

import {
  API_BASE_URL_STORAGE_KEY,
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
    expect(() => assertRuntimeApiUrl("http://api.example.test", "https:")).toThrow(/HTTPS/);
    expect(isLocalApiUrl("http://127.0.0.1:8000")).toBe(true);
    expect(isLocalApiUrl("https://api.example.test")).toBe(false);
  });

  it("prefers the build-time URL, then storage, and falls back safely", () => {
    const storage = {
      getItem: (key: string) => (key === API_BASE_URL_STORAGE_KEY ? "https://stored.example.test/" : null),
    };
    expect(resolveApiBaseUrl(storage, "https://configured.example.test/", "https:")).toBe(
      "https://configured.example.test",
    );
    expect(resolveApiBaseUrl(storage, undefined, "https:")).toBe("https://stored.example.test");
    expect(resolveApiBaseUrl({ getItem: () => "http://api.example.test" }, undefined, "https:")).toBe(
      DEFAULT_API_BASE_URL,
    );
  });
});
