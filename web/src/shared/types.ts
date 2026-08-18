export type AssignedCase = {
  case_id: string;
  work_label: string;
  case_lifecycle: string;
  commercial_stage: string;
  dce_availability: string;
};

export type FinancialCategory =
  | "SALES"
  | "DIRECT_COST"
  | "OVERHEAD"
  | "SUBCONTRACTING"
  | "CONTINGENCY"
  | "GROSS_MARGIN"
  | "FORECAST_CASHFLOW";

export type FinancialLine = {
  line_id: string;
  category: FinancialCategory;
  label: string;
  quantity_decimal: string;
  unit: string;
  amount_minor: number;
  currency_code: string;
};

export type FinancialSummary = {
  sales_total_minor: number;
  direct_cost_total_minor: number;
  overhead_total_minor: number;
  subcontracting_total_minor: number;
  contingency_total_minor: number;
  gross_margin_minor: number;
  gross_margin_rate_bps: number;
  forecast_cashflow_minor: number;
};

export type DraftReport = {
  report_id: string;
  case_id: string;
  status: "DRAFT";
  aggregate_revision: number;
  currency_code: string;
  calculated_at: string;
  ruleset_version: number;
  summary: FinancialSummary;
  lines: FinancialLine[];
};

export type CommandReceipt = {
  status: "SUCCEEDED";
  command_id: string;
  idempotency_key: string;
  result_code: string;
  aggregate_refs: Array<{
    aggregate_type: string;
    aggregate_id: string;
    aggregate_revision: number;
  }>;
  event_ids: string[];
  replayed: boolean;
};

export type PatronAssignment = {
  assignment_id: string;
  case_id: string;
  case_title: string;
  case_lifecycle: "ACTIVE" | "STOPPED" | "ARCHIVED";
  state: "ACTIVE" | "SUSPENDED" | "ENDED" | "EXPIRED";
  aggregate_revision: number;
  starts_at: string;
  ends_at: string | null;
  ended_at: string | null;
  scope_actions: string[];
  scope_classifications: ["INTERNAL_OPERATIONAL"];
};

export type PatronAssignmentJournalItem = {
  record_id: string;
  recorded_at: string;
  event_type:
    | "ASSIGNMENT_CREATED"
    | "ASSIGNMENT_SCOPE_AMENDED"
    | "ASSIGNMENT_SUSPENDED"
    | "ASSIGNMENT_REACTIVATED"
    | "ASSIGNMENT_ENDED";
  resulting_revision: number;
  resulting_state: PatronAssignment["state"];
  reason_code: string | null;
};

export type PatronAssignmentInteractions = {
  assignment_id: string;
  case_id: string;
  case_lifecycle: PatronAssignment["case_lifecycle"];
  items: Array<{
    record_id: string;
    kind: "ACKNOWLEDGEMENT" | "CLARIFICATION_REQUEST" | "UNAVAILABILITY_REPORT";
    recorded_at: string;
    operational_state: "RECORDED" | "OPEN";
    priority?: string | null;
    clarification_kind?: string | null;
    reason_kind?: string | null;
    known_deadline_impact?: boolean | null;
  }>;
};

export type ApiError = Error & { status?: number; detail?: string };
