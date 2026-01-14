import {
  Citation,
  EvidenceSupport,
  DebugCandidate,
  VersionSnapshot,
  AskRequest,
  AskResponse,
  RefusalCode,
} from "./generated";

export type {
  Citation,
  EvidenceSupport,
  DebugCandidate,
  VersionSnapshot,
  AskRequest,
  AskResponse,
  RefusalCode,
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  evidence?: EvidenceSupport;
  debug_candidates?: DebugCandidate[];
  refusal_code?: string;
  reason?: string;
  request_id?: string;
  version_snapshot?: VersionSnapshot;
};
