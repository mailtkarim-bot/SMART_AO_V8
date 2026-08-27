import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type {
  DecisionCctpPricingCrossingItem,
  DecisionDocumentContradictionItem,
} from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;

export function useDecisionCrossChecks(
  api: ApiClient,
  setMessage: SetMessage,
  caseId: string,
) {
  const [crossings, setCrossings] = useState<DecisionCctpPricingCrossingItem[]>([]);
  const [contradictions, setContradictions] = useState<DecisionDocumentContradictionItem[]>([]);
  const [loading, setLoading] = useState(false);

  async function refresh(targetCaseId = caseId) {
    if (!targetCaseId) {
      setCrossings([]);
      setContradictions([]);
      return;
    }
    setLoading(true);
    try {
      const [crossingPage, contradictionPage] = await Promise.all([
        api.crossCctpPricing(targetCaseId),
        api.listDocumentContradictions(targetCaseId),
      ]);
      setCrossings(crossingPage.items);
      setContradictions(contradictionPage.items);
    } catch (error) {
      setCrossings([]);
      setContradictions([]);
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger les contrôles croisés.",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    // The selected case is the resource key; refresh is intentionally imperative.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  return { crossings, contradictions, loading, refresh };
}
