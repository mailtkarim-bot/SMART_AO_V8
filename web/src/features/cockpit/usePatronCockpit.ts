import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type {
  PatronAssignment,
  PatronAssignmentInteractions,
  PatronAssignmentJournalItem,
} from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type SetMessage = Dispatch<SetStateAction<Message | null>>;

type CaseSelectionHandler = (caseId: string) => Promise<void>;

export function usePatronCockpit(
  api: ApiClient,
  setMessage: SetMessage,
  onCaseSelected: CaseSelectionHandler,
) {
  const [assignments, setAssignments] = useState<PatronAssignment[]>([]);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [journal, setJournal] = useState<PatronAssignmentJournalItem[]>([]);
  const [interactions, setInteractions] = useState<PatronAssignmentInteractions | null>(null);

  async function refreshAssignments() {
    try {
      const result = await api.listPatronAssignments();
      setAssignments(result.items);
      const first = result.items[0];
      if (first && !selectedAssignmentId) {
        setSelectedAssignmentId(first.assignment_id);
        await loadAssignmentDetails(first.assignment_id);
      }
    } catch (error) {
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger le cockpit patron.",
      });
    }
  }

  async function loadAssignmentDetails(assignmentId: string) {
    try {
      const [journalResult, interactionsResult] = await Promise.all([
        api.getAssignmentJournal(assignmentId),
        api.getAssignmentInteractions(assignmentId),
      ]);
      setJournal(journalResult.items);
      setInteractions(interactionsResult);
    } catch (error) {
      setJournal([]);
      setInteractions(null);
      setMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Impossible de charger le journal patron.",
      });
    }
  }

  async function selectAssignment(assignment: PatronAssignment) {
    setSelectedAssignmentId(assignment.assignment_id);
    await Promise.all([
      loadAssignmentDetails(assignment.assignment_id),
      onCaseSelected(assignment.case_id),
    ]);
  }

  return {
    assignments,
    selectedAssignmentId,
    journal,
    interactions,
    refreshAssignments,
    loadAssignmentDetails,
    selectAssignment,
  };
}
