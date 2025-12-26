export type Citation = {
  doc_id: string;
  doc_name: string;
  page_num: number;
  chunk_id: string;
  snippet: string;
  score: number;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  refusal_code?: string;
  request_id?: string;
};

export type VersionSnapshot = {
  request_id: string;
  docs_snapshot_id: string;
  prompt_version: string;
  retrieval_version: string;
  model_id: string;
  parser_mode: string;
};
