import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type {
  StructuredRiskProjection,
  TransitionStructuredRiskTreatmentInput,
} from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;
type DecisionSource = { aggregate_type: string; aggregate_id: string };

function riskIdsFromSources(sources: DecisionSource[]): string[] {
  return sources
    .filter((source) => source.aggregate_type === "DECISION_RISK")
    .map((source) => source.aggregate_id)
    .filter((riskId, index, values) => Boolean(riskId) && values.indexOf(riskId) === index);
}

export function useDecisionRisks(
  api: ApiClient,
  setMessage: SetMessage,
  caseId: string,
  sources: DecisionSource[],
) {
  const [risks, setRisks] = useState<StructuredRiskProjection[]>([]);
  const [loading, setLoading] = useState(false);
  const [transitioningRiskId, setTransitioningRiskId] = useState<string | null>(null);

  async function refresh(targetCaseId = caseId, targetSources = sources) {
    const riskIds = riskIdsFromSources(targetSources);
    if (!targetCaseId || riskIds.length === 0) {
      setRisks([]);
      return;
    }
    setLoading(true);
    try {
      const results = await Promise.all(
        riskIds.map((riskId) => api.getDecisionRisk(targetCaseId, riskId)),
      );
      setRisks(results);
    } catch (error) {
      setRisks([]);
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger les risques Decision.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function transitionRisk(
    risk: StructuredRiskProjection,
    input: Omit<TransitionStructuredRiskTreatmentInput, "expected_revision">,
  ) {
    if (!caseId || risk.treatment !== "OPEN") return;
    setTransitioningRiskId(risk.risk_id);
    try {
      await api.transitionDecisionRiskTreatment(caseId, risk.risk_id, {
        ...input,
        expected_revision: risk.revision,
      });
      await refresh();
      setMessage({
        tone: "success",
        text: `Traitement du risque ${risk.risk_code} enregistré : ${input.to_treatment}.`,
      });
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de traiter le risque.",
      });
    } finally {
      setTransitioningRiskId(null);
    }
  }

  useEffect(() => {
    void refresh();
    // The case and frozen Decision sources are the resource keys for this read model.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, JSON.stringify(sources)]);

  return { risks, loading, transitioningRiskId, refresh, transitionRisk };
}
