import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type {
  BoampObservation,
  BoampQualificationDecision,
  BoampQualificationForm,
  BoampQualificationReason,
} from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;

const initialForm: BoampQualificationForm = {
  decision: "QUALIFIED",
  reason_code: "RELEVANT_PUBLIC_SIGNAL",
};

export function useBoampOpportunities(api: ApiClient, setMessage: SetMessage) {
  const [observations, setObservations] = useState<BoampObservation[]>([]);
  const [selectedObservationId, setSelectedObservationId] = useState("");
  const [qualificationForm, setQualificationForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [qualifying, setQualifying] = useState(false);

  async function refreshObservations() {
    setLoading(true);
    try {
      const result = await api.listBoampObservations();
      setObservations(result.observations);
      if (
        selectedObservationId &&
        !result.observations.some((item) => item.observation_id === selectedObservationId)
      ) {
        setSelectedObservationId("");
      }
      if (!selectedObservationId && result.observations[0]) {
        setSelectedObservationId(result.observations[0].observation_id);
      }
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger les opportunités BOAMP.",
      });
    } finally {
      setLoading(false);
    }
  }

  function selectObservation(observationId: string) {
    setSelectedObservationId(observationId);
  }

  function setDecision(decision: BoampQualificationDecision) {
    setQualificationForm((current) => ({ ...current, decision }));
  }

  function setReason(reason_code: BoampQualificationReason) {
    setQualificationForm((current) => ({ ...current, reason_code }));
  }

  async function qualifySelected() {
    if (!selectedObservationId) {
      setMessage({ tone: "warning", text: "Sélectionnez une opportunité BOAMP avant de qualifier." });
      return;
    }
    setQualifying(true);
    try {
      const receipt = await api.qualifyBoampObservation(selectedObservationId, qualificationForm);
      setMessage({
        tone: "success",
        text: receipt.replayed ? "Qualification déjà enregistrée : rejeu idempotent." : "Qualification BOAMP enregistrée.",
      });
      await refreshObservations();
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible d’enregistrer la qualification BOAMP.",
      });
    } finally {
      setQualifying(false);
    }
  }

  return {
    observations,
    selectedObservationId,
    qualificationForm,
    loading,
    qualifying,
    refreshObservations,
    selectObservation,
    setDecision,
    setReason,
    qualifySelected,
  };
}
