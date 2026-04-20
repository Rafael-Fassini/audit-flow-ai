export type DocumentUploadResponse = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: string;
  created_at: string;
};

export type EvidenceSnippet = {
  section_index: number;
  chunk_index: number;
  text: string;
};

export type ProcessStep = {
  index: number;
  step_type: string;
  description: string;
  actors: string[];
  systems: string[];
  evidence: EvidenceSnippet;
};

export type NarrativeGap = {
  description: string;
  evidence: EvidenceSnippet;
};

export type AccountingProcess = {
  process_name: string;
  summary: string;
  source_filename: string;
  steps: ProcessStep[];
  account_references: unknown[];
  chart_of_accounts_references: unknown[];
  controls: unknown[];
  posting_logic: string[];
  narrative_gaps: NarrativeGap[];
};

export type FindingEvidence = {
  source: string;
  text: string;
  section_index?: number | null;
  chunk_index?: number | null;
  knowledge_chunk_id?: string | null;
  document_family?: string | null;
  document_scope?: string | null;
};

export type FindingScore = {
  severity: string;
  confidence: number;
  review_required: boolean;
};

export type ReportFinding = {
  id: string;
  finding_type: string;
  category: string;
  title: string;
  description: string;
  source: string;
  score: FindingScore;
  related_finding_ids: string[];
  evidence: FindingEvidence[];
};

export type FollowUpQuestion = {
  id: string;
  question: string;
  rationale: string;
  related_finding_ids: string[];
};

export type AnalysisSummary = {
  process_name: string;
  source_filename: string;
  total_findings: number;
  high_severity_findings: number;
  review_required_count: number;
};

export type ScopedConclusionEvidence = {
  finding_id: string;
  title: string;
  category: string;
  evidence_text: string;
};

export type ScopedQuestionAnswer = {
  question: string;
  conclusion: string;
  rationale: string;
  top_findings: ScopedConclusionEvidence[];
};

export type FinalResponseFinding = {
  title: string;
  category: string;
  severity: string;
  evidence: string;
};

export type FinalResponse = {
  conclusion: string;
  top_findings: FinalResponseFinding[];
  missing_items: string[];
  normative_rationale: string;
  recommended_action: string;
};

export type AnalysisReport = {
  analysis_id: string;
  status: string;
  generated_at: string;
  summary: AnalysisSummary;
  scoped_answer?: ScopedQuestionAnswer;
  final_response?: FinalResponse;
  process: AccountingProcess;
  findings: ReportFinding[];
  evidence: FindingEvidence[];
  follow_up_questions: FollowUpQuestion[];
};

export type ApiError = {
  detail?: unknown;
  error?: {
    code: string;
    message: string;
    request_id: string;
    details?: unknown;
  };
};
