import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type {
  DecisionPricingReconciliationItem,
  DecisionRiskRequirementLink,
} from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;

export function useDecisionRiskRequirements(api: ApiClient, setMessage: SetMessage, caseId: string) {
  const [links, setLinks] = useState<DecisionRiskRequirementLink[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [selectedLinkId, setSelectedLinkId] = useState("");
  const [pricingItems, setPricingItems] = useState<DecisionPricingReconciliationItem[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);

  async function refresh(targetCaseId = caseId) {
    if (!targetCaseId) {
      setLinks([]);
      setNextCursor(null);
      setSelectedLinkId("");
      setPricingItems([]);
      return;
    }
    setLoading(true);
    try {
      const page = await api.listDecisionRiskRequirementLinks(targetCaseId);
      setLinks(page.items);
      setNextCursor(page.next_cursor);
      setSelectedLinkId((current) =>
        page.items.some((item) => item.link_id === current) ? current : page.items[0]?.link_id ?? "",
      );
      setPricingItems([]);
    } catch (error) {
      setLinks([]);
      setNextCursor(null);
      setSelectedLinkId("");
      setPricingItems([]);
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger les liens Decision.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function loadMore() {
    if (!caseId || !nextCursor || loading) return;
    setLoading(true);
    try {
      const page = await api.listDecisionRiskRequirementLinks(caseId, 20, nextCursor);
      setLinks((current) => [...current, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger la page suivante.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function reconcilePricing() {
    const selectedLink = links.find((item) => item.link_id === selectedLinkId);
    const normalizedSearch = search.trim();
    if (!caseId || !selectedLink || normalizedSearch.length < 2) return;
    setSearching(true);
    try {
      const result = await api.reconcileDecisionPricing(
        caseId,
        selectedLink.link_id,
        normalizedSearch,
      );
      setPricingItems(result.items);
    } catch (error) {
      setPricingItems([]);
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de rapprocher le pricing.",
      });
    } finally {
      setSearching(false);
    }
  }

  useEffect(() => {
    void refresh();
    // The selected case is the resource key; refresh is intentionally imperative.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  return {
    links,
    nextCursor,
    selectedLinkId,
    pricingItems,
    search,
    loading,
    searching,
    setSearch,
    setSelectedLinkId,
    refresh,
    loadMore,
    reconcilePricing,
  };
}
