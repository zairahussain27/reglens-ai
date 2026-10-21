export interface User { id: number; name: string; email: string; role: string; workspace_id: number; workspace_name: string; has_password: boolean; google: boolean }
export interface AuthResult { token: string; user: User }

export interface Dashboard {
  profile: { complete: boolean; missing: string[]; completion_percent: number; review_required?: boolean };
  applicable_regulations: number; unknown_applicability?: number; compliance_score: number | null; compliance_assessments?: number; risk_score: number | null;
  risk_estimated?: boolean; risk_unknown_applicability?: number; risk_unassessed_findings?: number;
  open: number; overdue: number; by_area: Array<{ area: string; score: number }>;
  regulations: number; reports: number;
  latest: Array<{ id: number; title: string; regulator: string; date: string; applicable: boolean }>;
  assessment?: { created_at: string; counts: Record<string, number> } | null;
}
export interface Regulation { id: number; title: string; regulator: string; issued_on?: string | null; created_at: string; summary: string; status: string; applicable?: boolean; has_file: boolean; own: boolean; source_url?: string | null; ingestion_error?: string | null }
export interface Document { id: number; name: string; kind: string; created_at: string; status: string; use_in_ai: boolean; has_file: boolean; error?: string | null }
export interface AlertItem { id: number; title: string; detail: string; created_at: string; unread: boolean }
export interface Reminder { id: number; title: string; due: string; done: boolean; lead: number }
export interface Report { id: number; name: string; kind: string; created_at: string; created_by_name: string }
export interface Registration { registration_type: string; required_status: string; status: string; number: string; effective_date: string | null; expiry_date: string | null; document_id: number | null }
export type CompanyData = Record<string, unknown> & { registrations?: Registration[] };
export interface CompanyResponse { company: CompanyData; options: Record<string, string[]>; profile: { complete: boolean; dismissed: boolean; completion_percent: number; missing: string[] }; legal_name_change_used: boolean }
export interface FilingItem { id: number; kind: string; period: string; due_on?: string | null; paid_on?: string | null; amount?: number | null; status: string; reference: string; notes: string; has_file: boolean; file_name?: string | null; fy: string; overdue: boolean }
export interface FilingResponse { items: FilingItem[]; kinds: string[]; fys: string[]; summary: { paid_total: number; pending: number; overdue: number; by_kind?: Array<{ kind: string; paid: number }> } }
export interface AskResult { id: number; question: string; answer: string; sources: Array<{ doc: string; page?: number | null; snippet?: string }>; found: boolean; created_at: string }
export interface RiskContributor { title: string; applicability: string; compliance_status: string; severity: string; likelihood: string; score: number; reason: string }
export interface RiskRow { id: number; title: string; area: string; level: string; status: string; source: string; source_ref?: string | null; owner: string; owner_id: number | null; due?: string | null; ignored: boolean; classification: "confirmed" | "review"; compliance_status?: string; applicability?: string }
export interface RiskData { overall: string; open: number; overdue: number; resolved: number; assessment: { risk_score: number | null; risk_level: string; created_at: string; estimated: boolean; applicable_count: number; unknown_applicability_count: number; unassessed_count: number; contributors: RiskContributor[]; formula: string } | null; by_area: Array<{ area: string; score: number }>; register: RiskRow[]; members: Array<{ id: number; name: string }> }
export interface WorkspaceSettings { name: string; regulators: string[]; reminders: boolean; changes: boolean; weekly: boolean; default_lead: number }
export interface AIFinding { requirement: string; status: string; evidence: string; source: string; reasoning: string }
export interface Finding { id: number; title: string; source_url: string; applicability: string; applicability_reason: string; compliance_status: string; compliance_gap: string; action_recommendation: string; risk_contribution: number; risk_reason: string; severity: string; likelihood: string; recommendation: string; remediation_status: string; due_on?: string | null; evidence_ids: number[]; evidence_verified: boolean; missing_info: Array<{ question: string }>; ai_evaluated: boolean; ai_confidence: number | null; ai_summary: string; ai_findings: AIFinding[] }
export interface Assessment { id: number; created_at: string; status: string; compliance_score: number | null; risk_score: number | null; risk_level: string; risk_formula: string; risk_reasons: string[]; risk_contributors: RiskContributor[]; risk_estimated: boolean; applicable_count: number; unknown_applicability_count: number; unassessed_count: number; counts: Record<string, number>; critical_missing: string[]; findings?: Finding[] }
