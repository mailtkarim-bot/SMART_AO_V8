export const DEFAULT_API_BASE_URL = "http://localhost:8000";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

export function normalizeApiBaseUrl(rawUrl: string): string {
  const value = rawUrl.trim();
  if (!value) throw new Error("L’URL API est obligatoire.");

  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error("L’URL API doit être une URL HTTP ou HTTPS valide.");
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("L’URL API doit utiliser HTTP ou HTTPS.");
  }
  if (parsed.username || parsed.password) {
    throw new Error("L’URL API ne doit pas contenir d’identifiants.");
  }
  if (parsed.search || parsed.hash) {
    throw new Error("L’URL API ne doit pas contenir de query string ni de fragment.");
  }

  parsed.pathname = parsed.pathname.replace(/\/+$/, "");
  return parsed.toString().replace(/\/$/, "");
}

export function isLocalApiUrl(rawUrl: string): boolean {
  try {
    return LOCAL_HOSTS.has(new URL(normalizeApiBaseUrl(rawUrl)).hostname);
  } catch {
    return false;
  }
}

export function assertRuntimeApiUrl(
  rawUrl: string,
  pageProtocol: string,
  pageOrigin?: string,
): string {
  const normalized = normalizeApiBaseUrl(rawUrl);
  const parsed = new URL(normalized);
  if (pageProtocol === "https:" && !isLocalApiUrl(normalized)) {
    if (parsed.protocol !== "https:" || (pageOrigin && parsed.origin !== pageOrigin)) {
      throw new Error("Une page HTTPS ne peut utiliser que son origine API HTTPS.");
    }
  }
  return normalized;
}

export function resolveApiBaseUrl(
  configuredUrl: string | undefined,
  pageProtocol: string,
  pageOrigin?: string,
): string {
  const candidate =
    configuredUrl?.trim() ||
    (pageProtocol === "https:" && pageOrigin ? pageOrigin : DEFAULT_API_BASE_URL);
  try {
    return assertRuntimeApiUrl(candidate, pageProtocol, pageOrigin);
  } catch {
    return pageProtocol === "https:" && pageOrigin
      ? normalizeApiBaseUrl(pageOrigin)
      : DEFAULT_API_BASE_URL;
  }
}
