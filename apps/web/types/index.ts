export type Citation = {
  doc_id: string;
  doc_name: string;
  page_num: number;
  chunk_id: string;
  snippet: string;
  score: number;
};

export type EvidenceSupport = {
  verdict: "VERIFIED" | "UNVERIFIED";
  verifier_model?: string | null;
  evidence_grade: "A" | "B" | "C";
  evidence_label: "Strong" | "Moderate" | "Weak";
  support_count: number;
  top_rrf_score: number;
  rrf_margin: number;
  overlap_score: number;
  supporting_span: string;
  supporting_page_num: number;
  supporting_doc_name: string;
  docs_snapshot_id: string;
  index_version: string;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  evidence?: EvidenceSupport;
  refusal_code?: string;
  reason?: string;
  request_id?: string;
  version_snapshot?: VersionSnapshot;
};

export type VersionSnapshot = {
  request_id: string;
  docs_snapshot_id: string;
  prompt_version: string;
  retrieval_version: string;
  model_id: string;
  parser_mode: string;
};
