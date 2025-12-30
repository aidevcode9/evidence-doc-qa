import React from "react";
import { Message } from "@/types";
import { CitationCard } from "./CitationCard";

const REFUSAL_DESCRIPTIONS: Record<string, string> = {
  INJECTION_DETECTED: "This query was flagged as a potential security risk.",
  LOW_RETRIEVAL_CONFIDENCE: "I found some information, but it's not strong enough to answer reliably.",
  NO_SUPPORTING_EVIDENCE: "I couldn't find any relevant information in the document to answer this.",
  PARSE_FAILED: "The document content could not be processed correctly.",
  POLICY_REFUSAL: "This request was declined according to established safety policies.",
};

const GRADE_STYLES: Record<string, string> = {
  A: "bg-green-50 text-green-800 border-green-200",
  B: "bg-amber-50 text-amber-800 border-amber-200",
  C: "bg-red-50 text-red-800 border-red-200",
};

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const isRefusal = !!message.refusal_code;
  const evidence = message.evidence;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm transition-all ${
          isUser
            ? "bg-blue-600 text-white"
            : isRefusal
            ? "bg-red-50 text-red-900 border border-red-200"
            : "bg-gray-100 text-gray-800 border border-gray-200"
        }`}
      >
        <div className={`text-sm sm:text-base whitespace-pre-wrap ${isRefusal ? "font-medium italic opacity-70" : ""}`}>
          {isRefusal ? message.reason || message.text : message.text}
        </div>

        {message.refusal_code && (
          <div className="mt-3 p-3 bg-white border border-red-100 rounded-xl flex items-start gap-3 shadow-sm">
            <div className="mt-0.5 text-red-500 flex-shrink-0">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <p className="text-[10px] font-extrabold text-red-800 uppercase tracking-wider mb-0.5">
                {message.refusal_code.replace(/_/g, " ")}
              </p>
              <p className="text-[12px] text-red-700 leading-snug">
                {REFUSAL_DESCRIPTIONS[message.refusal_code] || "The system refused to answer based on safety or confidence policies."}
              </p>
            </div>
          </div>
        )}

        {evidence && !isRefusal && (
          <div className="mt-4 p-3 bg-white border border-gray-200 rounded-xl shadow-sm space-y-2">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-0.5 text-[10px] font-extrabold rounded border ${
                    GRADE_STYLES[evidence.evidence_grade]
                  }`}
                >
                  {evidence.evidence_grade}
                </span>
                <span className="text-xs font-semibold text-gray-700">
                  {evidence.evidence_label} Evidence
                </span>
              </div>
              <span
                className={`text-[10px] font-bold uppercase tracking-wider ${
                  evidence.verdict === "VERIFIED" ? "text-green-700" : "text-amber-700"
                }`}
              >
                {evidence.verdict === "VERIFIED"
                  ? `Verified by ${evidence.verifier_model || "LLM"}`
                  : "Unverified (human review)"}
              </span>
            </div>
            <div className="text-[11px] text-gray-600 flex flex-wrap gap-x-4 gap-y-1">
              <span>
                Support: {evidence.support_count} snippet{evidence.support_count === 1 ? "" : "s"}
              </span>
              <span>Index: {evidence.index_version}</span>
            </div>
            <div className="text-xs text-gray-700">
              <span className="font-semibold">Evidence mapping:</span>{" "}
              {evidence.supporting_doc_name} - Page {evidence.supporting_page_num} - "
              {evidence.supporting_span}"
            </div>
            <div className="text-[10px] text-gray-500 font-mono">
              SNAPSHOT: {evidence.docs_snapshot_id}
            </div>
          </div>
        )}

        {message.citations && message.citations.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200 space-y-3">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Sources</p>
            {message.citations.map((c, idx) => (
              <CitationCard key={idx} citation={c} />
            ))}
          </div>
        )}

        {message.request_id && (
          <div className="mt-2 text-[10px] text-gray-400 font-mono">
            REQ-ID: {message.request_id}
          </div>
        )}
      </div>
    </div>
  );
}
