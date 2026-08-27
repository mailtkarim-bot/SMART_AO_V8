import { useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type {
  DceContractRiskSignal,
  RegisterStructuredRiskInput,
} from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;

export function useDceContractRiskSignals(
  api: ApiClient,
  setMessage: SetMessage,
  caseId: string,
) {
  const [signals, setSignals] = useState<DceContractRiskSignal[]>([]);
  const [loading, setLoading] = useState(false);
  const [registeringObservationId, setRegisteringObservationId] = useState<string | null>(null);

  async function refresh(targetCaseId = caseId) {
    if (!targetCaseId) {
      setSignals([]);
      return;
    }
    setLoading(true);
    try {
      const result = await api.listDceContractRiskSignals(targetCaseId);
      setSignals(result.items);
    } catch (error) {
      setSignals([]);
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger les signaux contractuels.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function registerSignal(signal: DceContractRiskSignal, input: RegisterStructuredRiskInput) {
    if (!caseId) return;
    setRegisteringObservationId(signal.observation_id);
    try {
      await api.registerStructuredRisk(caseId, input);
      setSignals((current) => current.filter((item) => item.observation_id !== signal.observation_id));
      setMessage({
        tone: "success",
        text: `Risque ${input.risk_code} enregistré avec la preuve ${signal.source_locator_label}.`,
      });
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible d’enregistrer le risque structuré.",
      });
    } finally {
      setRegisteringObservationId(null);
    }
  }

  useEffect(() => {
    void refresh();
    // The selected case is the resource key; refresh is intentionally imperative.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  return { signals, loading, registeringObservationId, refresh, registerSignal };
}
