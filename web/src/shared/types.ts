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

export type ApiError = Error & { status?: number; detail?: string };
