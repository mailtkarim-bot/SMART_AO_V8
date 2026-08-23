import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type { CaseDceReading, KnowledgeSearchResult } from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;

export function useDceKnowledge(
  api: ApiClient,
  setMessage: SetMessage,
  selectedCaseId: string,
) {
  const [reading, setReading] = useState<CaseDceReading | null>(null);
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);

  async function loadReading(caseId = selectedCaseId) {
    if (!caseId) {
      setReading(null);
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      setReading(await api.getCaseDceReading(caseId));
    } catch (error) {
      setReading(null);
      if ((error as { status?: number }).status === 404) return;
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger la lecture DCE.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function searchKnowledge() {
    const normalized = query.trim();
    if (!selectedCaseId) {
      setMessage({ tone: "warning", text: "Sélectionnez une affaire avant de rechercher dans le DCE." });
      return;
    }
    if (!normalized) {
      setMessage({ tone: "warning", text: "Saisissez un terme de recherche DCE." });
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const response = await api.searchCaseKnowledge(selectedCaseId, normalized, 5);
      setResults(response.results);
    } catch (error) {
      setResults([]);
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Recherche knowledge indisponible.",
      });
    } finally {
      setSearching(false);
    }
  }

  function resetSearch() {
    setQuery("");
    setResults([]);
  }

  return {
    reading,
    results,
    query,
    loading,
    searching,
    setQuery,
    loadReading,
    searchKnowledge,
    resetSearch,
  };
}
