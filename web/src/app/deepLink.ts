export const NAV_KEYS = [
  "overview",
  "create-case",
  "preparation",
  "review",
  "opportunities",
  "dce",
  "wizard",
  "library",
  "decision",
  "submission",
] as const;

export type NavKey = (typeof NAV_KEYS)[number];

type DeepLinkState = {
  caseId: string;
  section: NavKey;
};

const DEFAULT_SECTION: NavKey = "overview";

export function readDeepLink(hash: string): DeepLinkState {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const section = params.get("section");
  return {
    caseId: params.get("case")?.trim() ?? "",
    section: isNavKey(section) ? section : DEFAULT_SECTION,
  };
}

export function buildDeepLink({ caseId, section }: DeepLinkState): string {
  const params = new URLSearchParams();
  if (caseId.trim()) params.set("case", caseId.trim());
  if (section !== DEFAULT_SECTION) params.set("section", section);
  const query = params.toString();
  return query ? `#${query}` : "";
}

function isNavKey(value: string | null): value is NavKey {
  return value !== null && (NAV_KEYS as readonly string[]).includes(value);
}
