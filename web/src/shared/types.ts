export type AssignedCase = {
  case_id: string;
  work_label: string;
  case_lifecycle: string;
  commercial_stage: string;
  dce_availability: string;
};

export type CreateCaseInput = {
  title: string;
  object_description: string;
  scope_kind: "SINGLE_LOT" | "MULTI_LOT" | "TRANCHE" | "VARIANT" | "CUSTOM";
  lot_numbers: string[];
  tranche_reference?: string;
  variant_reference?: string;
  scope_justification?: string;
  origin_kind?: "MANUAL" | "OPPORTUNITY" | "IMPORT" | "CLIENT_REQUEST";
};

export type CreateCaseResponse = {
  status: "SUCCEEDED";
  command_id: string;
  idempotency_key: string;
  result_code: "CASE_CREATED";
  case_id: string;
  version: number;
  event_ids: string[];
  navigation: "CASE_OVERVIEW";
  replayed: boolean;
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

export type PatronAction = {
  action_id: string;
  case_id: string | null;
  functional_key: string;
  action_type: "REVIEW_PREPARATION" | "CONTROL_SUBMISSION" | "VALIDATE_PRICE" | "DECIDE_GO_NO_GO";
  severity: "URGENT" | "BLOCKING" | "AT_RISK" | "MONITOR";
  state: "OPEN" | "IN_PROGRESS" | "WAITING" | "COMPLETED" | "ABANDONED";
  title: string;
  why_now: string;
  impact: string;
  recommended_action: string;
  due_at: string | null;
  source_refs: string[];
  aggregate_revision: number;
};

export type DecisionContextReferenceInput = {
  aggregate_type: "CASE" | "DCE_VERSION" | "DCE_REQUIREMENT" | "DECISION_RISK" | "PRICING_SCENARIO";
  aggregate_id: string;
  aggregate_revision: number;
  content_hash?: string;
  reference_role: string;
};

export type CreateDecisionRequest = {
  scope_fingerprint?: string;
  command_id?: string;
  idempotency_key?: string;
};

export type FreezeDecisionContextRequest = {
  context_id: string;
  expected_revision: number;
  rationale: string;
  unknowns?: string[];
  risks?: string[];
  references: DecisionContextReferenceInput[];
  command_id?: string;
  idempotency_key?: string;
};

export type ResolveDecisionConditionRequest = {
  transition_id?: string;
  expected_revision: number;
  target_status: "SATISFIED" | "FAILED";
  evidence_reference?: string;
  failure_reason?: string;
  command_id?: string;
  idempotency_key?: string;
};

type DecisionCommandReceipt = Omit<CommandReceipt, "result_code"> & {
  result_code: string;
};

export type CreateDecisionResponse = DecisionCommandReceipt & {
  result_code: "DECISION_DRAFT_CREATED";
  decision_id: string;
  version: number;
};

export type FreezeDecisionContextResponse = DecisionCommandReceipt & {
  result_code: "DECISION_CONTEXT_FROZEN";
  decision_id: string;
  context_id: string;
  fingerprint: string;
  version: number;
};

export type ResolveDecisionConditionResponse = DecisionCommandReceipt & {
  result_code: "DECISION_CONDITION_RESOLVED";
  decision_id: string;
  condition_id: string;
  status: "SATISFIED" | "FAILED";
  version: number;
};

export type ConditionalGoConditionRequest = {
  condition_id: string;
  label: string;
  owner_actor_id: string;
  due_at?: string;
  due_date_absence_reason?: string;
  failure_consequence: string;
};

export type FinalizeGoNoGoDecisionRequest = {
  expected_revision: number;
  displayed_fingerprint: string;
  outcome: "GO" | "CONDITIONAL_GO" | "NO_GO";
  justification: string;
  conditions?: ConditionalGoConditionRequest[];
  command_id?: string;
  idempotency_key?: string;
};

export type FinalizeGoNoGoDecisionResponse = DecisionCommandReceipt & {
  result_code: "DECISION_FINALIZED";
  decision_id: string;
  outcome: "GO" | "CONDITIONAL_GO" | "NO_GO";
  condition_count: number;
  version: number;
};

export type PatronDecisionDossier = {
  decision_id: string;
  aggregate_revision: number;
  case_id: string;
  decision_type: string;
  lifecycle: string;
  outcome: string;
  validity: string;
  context_status: string;
  final_justification: string | null;
  known: unknown[];
  unknowns: unknown[];
  risks: unknown[];
  conditions: Array<{ condition_id: string; label: string; status: string; due_at: string | null; failure_consequence: string }>;
  sources: Array<{ aggregate_type: string; aggregate_id: string; aggregate_revision: number; role: string }>;
  context_fingerprint: string | null;
};

export type StructuredRiskTreatment = "OPEN" | "ACCEPTED" | "MITIGATED";
export type StructuredRiskSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type StructuredRiskLikelihood = "RARE" | "POSSIBLE" | "LIKELY" | "ALMOST_CERTAIN";

export type StructuredRiskProjection = {
  risk_id: string;
  case_id: string;
  dce_version_id: string;
  risk_code: string;
  category: "CCAP" | "CCTP";
  title: string;
  severity: StructuredRiskSeverity;
  likelihood: StructuredRiskLikelihood;
  treatment: StructuredRiskTreatment;
  revision: number;
  due_at: string | null;
  latest_treatment_evidence: {
    locator: Record<string, unknown>;
    start_byte_offset: number;
    end_byte_offset: number;
    excerpt: string;
    rationale: string;
  } | null;
};

export type TransitionStructuredRiskTreatmentInput = {
  expected_revision: number;
  to_treatment: Exclude<StructuredRiskTreatment, "OPEN">;
  evidence_excerpt: string;
  evidence_locator: Record<string, unknown>;
  evidence_start_byte_offset: number;
  evidence_end_byte_offset: number;
  rationale: string;
};

export type StructuredRiskCommandResponse = CommandReceipt & {
  result_code: "DECISION_RISK_TREATMENT_TRANSITIONED";
  risk_id: string;
  version: number;
  treatment: Exclude<StructuredRiskTreatment, "OPEN">;
};

export type DecisionRiskRequirementLink = {
  link_id: string;
  case_id: string;
  risk_id: string;
  requirement_id: string;
  dce_version_id: string;
  relationship: string;
  rationale: string;
  source_refs: string[];
  created_at: string;
  action_id: string | null;
  action_state: string | null;
  action_severity: string | null;
  action_revision: number | null;
};

export type DecisionRiskRequirementPage = {
  items: DecisionRiskRequirementLink[];
  next_cursor: string | null;
};

export type DecisionPricingReconciliationItem = {
  link_id: string;
  batch_id: string;
  document_kind: string;
  batch_state: string;
  row_number: number;
  code: string | null;
  designation: string | null;
  unit: string | null;
  match_basis: string;
  verification_status: string;
};

export type DecisionPricingReconciliationResponse = {
  link_id: string;
  search: string;
  items: DecisionPricingReconciliationItem[];
};

export type PricingScenario = {
  scenario_id: string;
  case_id: string;
  scenario_key: string;
  scenario_type: string;
  version: number;
  state: "DRAFT" | "SELECTED" | "ARCHIVED";
  assumptions: Record<string, unknown>;
  sales_total_minor: number;
  total_cost_minor: number;
  gross_margin_minor: number;
  gross_margin_rate_bps: number;
  source_snapshot_revision: number;
};

export type EnterpriseDocumentKind = "INSURANCE" | "KBIS" | "RIB";

export type EnterpriseDocument = {
  document_id: string;
  document_kind: EnterpriseDocumentKind;
  document_label: string;
  issued_at: string;
  expires_at: string | null;
  verification_status: "PENDING" | "VALIDATED" | "EXPIRED" | "REJECTED";
  verification_revision: number;
};

export type EnterpriseCompany = {
  company_id: string;
  aggregate_revision: number;
  legal_name: string;
  trade_name: string | null;
  siren: string;
  siret: string;
  vat_number: string;
  address_line1: string;
  postal_code: string;
  city: string;
  country_code: string;
  documents: EnterpriseDocument[];
};

export type EnterpriseReceipt = CommandReceipt;

export type EnterpriseUploadReceipt = {
  upload_id: string;
  state: "CLEAN";
};

export type EnterpriseCompanyInput = {
  legal_name: string;
  trade_name?: string;
  siren: string;
  siret: string;
  vat_number: string;
  address_line1: string;
  postal_code: string;
  city: string;
  country_code: string;
};

export type EnterpriseDocumentUploadInput = {
  document_kind: EnterpriseDocumentKind;
  document_label: string;
  original_filename: string;
  expected_byte_size: number;
  expires_at: string;
};

export type EnterpriseCapabilityKind = "QUALIFICATION" | "REFERENCE" | "EQUIPMENT" | "TEAM" | "METHOD";

export type EnterpriseCapabilityVersion = {
  version_id: string;
  version_number: number;
  title: string;
  description: string;
  valid_from: string;
  valid_until: string | null;
  usage_scope: string;
  proof_document_ids: string[];
};

export type EnterpriseCapability = {
  capability_id: string;
  company_id: string;
  aggregate_revision: number;
  capability_kind: EnterpriseCapabilityKind;
  name: string;
  summary: string;
  state: "ACTIVE" | "SUSPENDED" | "RETIRED";
  versions: EnterpriseCapabilityVersion[];
};

export type EnterpriseCapabilityInput = {
  capability_kind: EnterpriseCapabilityKind;
  name: string;
  summary: string;
  state?: "ACTIVE" | "SUSPENDED" | "RETIRED";
};

export type EnterpriseCapabilityVersionInput = {
  expected_revision: number;
  title: string;
  description: string;
  valid_from: string;
  valid_until?: string;
  usage_scope: string;
  proof_document_ids?: string[];
};

export type EnterpriseDocumentVerificationInput = {
  expected_verification_revision: number;
  outcome: "VALIDATED" | "REJECTED";
  reason_code:
    | "DOCUMENT_ACCEPTED"
    | "DOCUMENT_ILLEGIBLE"
    | "DOCUMENT_EXPIRED"
    | "DOCUMENT_MISMATCH"
    | "DOCUMENT_DUPLICATE";
};

export type PricingImportRow = {
  row_number: number;
  code: string | null;
  designation: string | null;
  unit: string | null;
  quantity_decimal: string | null;
  unit_price_minor: number | null;
  total_minor: number | null;
  errors: string[];
};

export type PricingImportBatchRead = {
  batch_id: string;
  case_id: string;
  document_kind: "DPGF" | "BPU" | "EXCEL";
  state: "PREVIEWED" | "COMMITTED";
  aggregate_revision: number;
  row_count: number;
  valid_row_count: number;
  error_count: number;
  total_minor: number;
  rows: PricingImportRow[];
};

export type PricingImportPreview = PricingImportBatchRead & {
  filename: string;
  truncated: boolean;
  limit_reason: "ROW_LIMIT" | "ERROR_LIMIT" | null;
  result_code: "PRICING_IMPORT_PREVIEWED";
  command_id: string;
  idempotency_key: string;
  event_ids: string[];
  replayed: boolean;
};

export type CommitPricingImportRequest = {
  command_id: string;
  idempotency_key: string;
  correlation_id?: string;
  report_id: string;
  expected_batch_revision: number;
  expected_report_revision: number;
};

export type PricingImportCommitReceipt = {
  status: "SUCCEEDED";
  command_id: string;
  idempotency_key: string;
  result_code: "PRICING_IMPORT_COMMITTED";
  aggregate_refs: Array<{
    aggregate_type: string;
    aggregate_id: string;
    aggregate_revision: number;
  }>;
  event_ids: string[];
  replayed: boolean;
};

export type SubmissionPackageReceipt = CommandReceipt & {
  result_code: "SUBMISSION_PACKAGE_PREPARED";
};

export type SubmissionEvidenceReceipt = CommandReceipt & {
  result_code: "SUBMISSION_EVIDENCE_RECORDED";
  external_submission: "NOT_PERFORMED";
};

export type SubmissionSignatureReceipt = CommandReceipt & {
  result_code: "SUBMISSION_SIGNATURE_REQUESTED" | "SUBMISSION_SIGNATURE_RECORDED";
  external_submission: "NOT_PERFORMED";
};

export type SubmissionSignatureProjection = {
  signature_id: string;
  submission_package_id: string;
  case_id: string;
  provider: string;
  status: "REQUESTED" | "SIGNED" | "REJECTED";
  expected_package_version: number;
  revision: 1 | 2;
  external_submission: "NOT_PERFORMED";
};

export type DecisionDossierItem = Record<string, unknown>;

export type PreparationReadiness = {
  readiness_id: string;
  revision: number;
  state: "READY" | "READY_WITH_WARNINGS" | "BLOCKED";
  blocker_codes: string[];
  warning_codes: string[];
  checked_requirement_count: number;
  checked_task_count: number;
};

export type GeneratedDocument = {
  document_id: string;
  version: number;
  document_kind: "TECHNICAL_RESPONSE" | "DC1" | "DC2" | "DC4";
  state: "GENERATED" | "FAILED_SAFE";
  readiness_revision: number;
};

export type PreparationPackage = {
  package_id: string;
  case_id: string;
  assignment_id: string;
  dce_version_id: string;
  state: "IN_PREPARATION" | "A_REVIEW" | "READY" | "BLOCKED" | "GENERATED";
  aggregate_revision: number;
  latest_readiness: PreparationReadiness | null;
  generated_documents: GeneratedDocument[];
};

export type CollaboratorTask = {
  task_id: string;
  case_id: string;
  assignment_id: string;
  requirement_id: string | null;
  task_kind: string;
  title: string;
  objective: string;
  priority: "URGENT" | "HIGH" | "NORMAL" | "LOW";
  state: "OPEN" | "CLAIMED" | "IN_PROGRESS" | "BLOCKED" | "COMPLETED" | "NOT_APPLICABLE";
  due_at: string | null;
  aggregate_revision: number;
};

export type CollaboratorTaskList = {
  case_id: string;
  tasks: CollaboratorTask[];
};

export type InformationResponse = {
  response_id: string;
  request_revision: number;
  outcome: "ANSWERED" | "NOT_AVAILABLE" | "NEEDS_CLARIFICATION";
  response_text: string;
  source_locator: string | null;
  created_at: string;
};

export type InformationRequest = {
  request_id: string;
  task_id: string;
  request_kind: "MISSING_SOURCE" | "CLARIFICATION" | "OWNER_CONFIRMATION" | "DEADLINE_CONFIRMATION";
  subject: string;
  question: string;
  requested_object: string;
  reason: string;
  priority: "LOW" | "NORMAL" | "HIGH" | "CRITICAL";
  state: "OPEN" | "ANSWERED" | "CLOSED" | "CANCELLED";
  due_at: string | null;
  aggregate_revision: number;
  responses: InformationResponse[];
};

export type TaskBlocker = {
  blocker_id: string;
  task_id: string;
  task_revision: number;
  blocker_kind: "MISSING_INFORMATION" | "EXTERNAL_DEPENDENCY" | "SOURCE_CONFLICT" | "REVIEW_REQUIRED";
  description: string;
  source_locator: string | null;
  resolution_owner: "COLLABORATEUR" | "PATRON_ADMIN" | "EXTERNAL_PARTY";
  state: "OPEN" | "RESOLVED";
  resolution_note: string | null;
  resolved_at: string | null;
};

export type CollaboratorTaskWorkflow = {
  task_id: string;
  state: CollaboratorTask["state"];
  aggregate_revision: number;
  information_requests: InformationRequest[];
  blockers: TaskBlocker[];
};

export type CreateInformationRequestInput = {
  expected_task_revision: number;
  request_kind: InformationRequest["request_kind"];
  subject: string;
  question: string;
  requested_object: string;
  reason: string;
  priority: InformationRequest["priority"];
  due_at?: string | null;
};

export type RecordInformationResponseInput = {
  expected_revision: number;
  response_text: string;
  source_locator?: string | null;
  outcome: InformationResponse["outcome"];
};

export type DeclareTaskBlockerInput = {
  expected_revision: number;
  blocker_kind: TaskBlocker["blocker_kind"];
  description: string;
  source_locator?: string | null;
  resolution_owner: TaskBlocker["resolution_owner"];
};

export type ResolveTaskBlockerInput = {
  expected_revision: number;
  resolution_note: string;
};

export type PreparationReviewCorrection = {
  correction_id: string;
  review_revision: number;
  revision: number;
  target_document_id: string;
  correction_code: "SOURCE_MISSING" | "SOURCE_WRONG" | "SECTION_INCOMPLETE" | "WORDING_UNCLEAR";
  instruction: string;
  source_locator: string | null;
};

export type PreparationReview = {
  review_id: string;
  package_id: string;
  target_document_id: string;
  target_version: number;
  revision: number;
  state: "REQUESTED" | "ACCEPTED" | "RETURNED_WITH_CORRECTIONS" | "REJECTED";
  decision_code: "ACCEPTED" | "CORRECTIONS_REQUIRED" | "REJECTED" | null;
  decision_note: string | null;
  corrections: PreparationReviewCorrection[];
};

export type PreparationReviewList = {
  package_id: string;
  reviews: PreparationReview[];
};

export type RequestPreparationReviewInput = {
  expected_package_revision: number;
  target_document_id: string;
  target_version: number;
};

export type DecidePreparationReviewInput = {
  expected_review_revision: number;
  review_id: string;
  target_document_id: string;
  decision_code: PreparationReview["decision_code"] & string;
  decision_note?: string | null;
};

export type AddPreparationCorrectionInput = {
  review_id: string;
  target_document_id: string;
  correction_code: PreparationReviewCorrection["correction_code"];
  instruction: string;
  source_locator?: string | null;
};

export type TotpEnrollment = {
  factor_id: string;
  otpauth_uri: string;
  recovery_codes: string[];
  expires_at: string;
};

export type TotpStepUpResponse = {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  used_recovery_code: boolean;
};

export type BackendReadiness = {
  status: "ok" | "not_ready";
  service: "smart-ao-v8";
  checks: {
    database: "unknown" | "ok" | "failed";
    schema: "unknown" | "ok" | "failed";
    clamav: "unknown" | "ok" | "failed";
  };
};


export type AuthSession = {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
};

export type ActorKind = "PATRON_ADMIN" | "PATRON_DELEGATE" | "COLLABORATEUR";
export type MembershipState = "ACTIVE" | "SUSPENDED" | "REVOKED";

export type CurrentActor = {
  actor_id: string;
  identity_id: string;
  actor_kind: ActorKind;
  membership_state: MembershipState;
};


export type BoampObservation = {
  observation_id: string;
  source_notice_id: string;
  title: string | null;
  publication_date: string | null;
  response_deadline: string | null;
  department_codes: string[];
  market_types: string[];
  source_status: string | null;
  score_version: string;
  score: number;
  score_explanation: Record<string, unknown>;
  fingerprint_sha256: string;
};

export type BoampQualificationDecision = "QUALIFIED" | "REJECTED" | "SNOOZED";
export type BoampQualificationReason =
  | "RELEVANT_PUBLIC_SIGNAL"
  | "NOT_RELEVANT"
  | "INSUFFICIENT_PUBLIC_DATA"
  | "EXPIRED";

export type BoampQualificationInput = {
  decision: BoampQualificationDecision;
  reason_code: BoampQualificationReason;
};

export type BoampQualificationReceipt = {
  qualification_id: string;
  event_id: string;
  replayed: boolean;
};

export type BoampQualificationForm = {
  decision: BoampQualificationDecision;
  reason_code: BoampQualificationReason;
};

export type BoampOpportunity = BoampObservation;


export type CaseDceReading = {
  case_id: string;
  work_label: string;
  case_lifecycle: string;
  commercial_stage: string;
  dce_freshness: string;
  availability: "AVAILABLE";
  dce: {
    dce_version_id: string;
    lifecycle: string;
    integrity: string;
    classification_readiness: string;
    analysis_readiness: string;
    source_received_at: string;
  };
  counters: {
    total: number;
    pending_human_confirmation: number;
    confirmed: number;
    review_required: number;
    not_applicable: number;
  };
  requirements: Array<{
    requirement_id: string;
    requirement_type: string;
    directive_signal: string;
    confirmation_outcome: string;
    uncertainty_status: string;
    document_family: string;
    source_locator_label: string;
  }>;
};

export type KnowledgeSearchResult = {
  source_fragment_id: string;
  dce_version_id: string;
  score: number;
  locator: Record<string, unknown>;
  embedding_model: string;
};

export type KnowledgeSearchResponse = {
  case_id: string;
  query: string;
  results: KnowledgeSearchResult[];
};
