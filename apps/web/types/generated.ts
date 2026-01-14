/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

export type RefusalCode =
  | "NO_SUPPORTING_EVIDENCE"
  | "LOW_RETRIEVAL_CONFIDENCE"
  | "INJECTION_DETECTED"
  | "PARSE_FAILED"
  | "POLICY_REFUSAL";

export interface AskRequest {
  question: string;
  docs_snapshot_id?: string | null;
  top_k?: number | null;
  include_debug?: boolean | null;
}
export interface AskResponse {
  request_id: string;
  answer_text?: string | null;
  citations?: Citation[] | null;
  refusal_code?: RefusalCode | null;
  reason?: string | null;
  evidence?: EvidenceSupport | null;
  debug_candidates?: DebugCandidate[] | null;
  version_snapshot: VersionSnapshot;
}
export interface Citation {
  doc_id: string;
  doc_name: string;
  page_num: number;
  chunk_id: string;
  snippet: string;
  highlighted_text?: string | null;
  score: number;
}
export interface EvidenceSupport {
  verdict: string;
  verifier_model?: string | null;
  evidence_grade: string;
  evidence_label: string;
  support_count: number;
  top_rrf_score?: number | null;
  azure_search_score?: number | null;
  azure_reranker_score?: number | null;
  reranker_score?: number;
  rrf_margin: number;
  overlap_score: number;
  supporting_span: string;
  supporting_page_num: number;
  supporting_doc_name: string;
  docs_snapshot_id: string;
  index_version: string;
}
export interface DebugCandidate {
  doc_id: string;
  doc_name: string;
  page_num: number;
  chunk_id: string;
  rrf_score?: number | null;
  azure_search_score?: number | null;
  azure_reranker_score?: number | null;
  overlap_score: number;
  verifier_verdict: string;
  reason: string;
  snippet: string;
}
export interface VersionSnapshot {
  request_id: string;
  docs_snapshot_id: string;
  prompt_version: string;
  verifier_prompt_version?: string | null;
  retrieval_version: string;
  model_id: string;
  parser_mode: string;
}
