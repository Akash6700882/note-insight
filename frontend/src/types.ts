// Mirror of the backend Pydantic contract. Keep in sync with backend/app/schemas.py.

export type DocumentationStatus =
  | "well_documented"
  | "ambiguous"
  | "mentioned_without_plan";

export type ReviewStatus = "pending" | "reviewed";
export type AnalysisStatus = "success" | "failed";

export type ConditionOrigin =
  | "ai"
  | "ai_edited"
  | "ai_rejected"
  | "human_added";

export interface AiCondition {
  name: string;
  evidence_quote: string;
  documentation_status: DocumentationStatus;
  icd10_code: string;
  confidence: number;
  evidence_verified: boolean;
}

export interface ReviewedCondition extends AiCondition {
  origin: ConditionOrigin;
}

export interface AnalysisOut {
  id: string;
  status: AnalysisStatus;
  model_name: string;
  prompt_version: string;
  created_at: string;
  conditions: AiCondition[];
  documentation_gaps: string[];
  summary: string;
  error: string | null;
}

export interface ReviewOut {
  review_status: ReviewStatus;
  conditions: ReviewedCondition[];
  documentation_gaps: string[];
  summary: string;
  updated_at: string | null;
}

export interface NoteSummary {
  id: string;
  pseudonym: string | null;
  visit_date: string | null;
  created_at: string;
  condition_count: number;
  review_status: ReviewStatus;
}

export interface NoteDetail {
  id: string;
  text: string;
  pseudonym: string | null;
  visit_date: string | null;
  created_at: string;
  analysis: AnalysisOut | null;
  review: ReviewOut;
}

export interface NoteCreate {
  text: string;
  pseudonym?: string | null;
  visit_date?: string | null;
}

export interface ReviewSubmit {
  conditions: ReviewedCondition[];
  documentation_gaps: string[];
  summary: string;
}
