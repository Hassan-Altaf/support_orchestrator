/**
 * TypeScript types mirroring the backend Pydantic models exactly.
 *
 * Kept hand-typed (not OpenAPI-generated) for the take-home so the contract
 * is visible in one place. A production-grade version would generate this
 * from /openapi.json via `openapi-typescript` to prevent drift.
 */

// ---- Enums ------------------------------------------------------------

export const ISSUE_CATEGORIES = [
  "technical_bug",
  "account_access",
  "billing",
  "feature_request",
  "how_to",
  "outage",
  "other",
] as const;
export type IssueCategory = (typeof ISSUE_CATEGORIES)[number];

export const PRIORITIES = ["low", "medium", "high", "critical"] as const;
export type Priority = (typeof PRIORITIES)[number];

export const URGENCIES = ["not_urgent", "normal", "urgent", "immediate"] as const;
export type Urgency = (typeof URGENCIES)[number];

export type TraceOutcome = "ok" | "retry" | "fallback" | "error";

// ---- Domain models ----------------------------------------------------

export interface Classification {
  category: IssueCategory;
  priority: Priority;
  escalation_required: boolean;
  confidence: number;
  reasoning: string;
}

export interface ExtractedInfo {
  product_area: string;
  issue_summary: string;
  urgency: Urgency;
  suggested_tags: string[];
  affected_features: string[];
}

export interface EscalationContext {
  severity_level: number;
  suggested_team: string;
  sla_minutes: number;
  reason: string;
}

export interface InternalSummary {
  headline: string;
  customer_intent: string;
  diagnostic_notes: string;
  recommended_actions: string[];
  handoff_team: string;
}

export interface TraceEntry {
  node: string;
  duration_ms: number;
  outcome: TraceOutcome;
  detail: string | null;
}

export interface TicketProcessingResult {
  request_id: string;
  processed_at: string;
  classification: Classification;
  extracted_info: ExtractedInfo;
  escalation_context: EscalationContext | null;
  customer_response: string;
  internal_summary: InternalSummary;
  processing_trace: TraceEntry[];
  recovered_errors: string[];
}

// ---- Request / error envelope ----------------------------------------

export interface ProcessRequest {
  message: string;
  metadata?: Record<string, unknown> | null;
}

export interface ErrorResponse {
  error: string;
  detail: string | null;
  request_id: string | null;
}

export interface HealthResponse {
  status: string;
  version: string;
}
