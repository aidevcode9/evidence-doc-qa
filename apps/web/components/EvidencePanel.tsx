import React from "react";
import { Message } from "@/types";

const MetricTooltip = ({ label, description }: { label: string; description: string }) => (
  <span className="flex items-center gap-2">
    <span>{label}</span>
    <span
      className="text-[10px] text-gray-500 border border-white/10 rounded-full w-4 h-4 flex items-center justify-center cursor-help"
      title={description}
    >
      i
    </span>
  </span>
);

export function EvidencePanel({ message }: { message: Message | null }) {
  if (!message) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-gray-600 p-8 text-center border-l border-white/5 bg-white/[0.02]">
        <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <h3 className="text-sm font-display font-medium text-gray-400">Evidence Monitor</h3>
        <p className="text-xs text-gray-600 mt-2 max-w-[200px]">
          Select a response to view its verified evidence chain and confidence score.
        </p>
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="h-full flex flex-col items-center justify-center text-gray-600 p-8 text-center border-l border-white/5 bg-white/[0.02]">
        <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <h3 className="text-sm font-display font-medium text-gray-400">Evidence Monitor</h3>
        <p className="text-xs text-gray-600 mt-2 max-w-[200px]">
          Select an assistant response to review its evidence and citations.
        </p>
      </div>
    );
  }

  if (message.refusal_code) {
    const { evidence, citations, refusal_code, version_snapshot, debug_candidates } = message;
    return (
      <div className="h-full overflow-y-auto border-l border-white/5 bg-white/[0.02] flex flex-col font-sans">
        <div className="p-6 border-b border-white/5">
          <div className="text-[10px] font-bold uppercase tracking-widest text-red-400 mb-2">
            Refusal Is The Correct Answer
          </div>
          <h2 className="text-sm font-display font-semibold text-gray-200 mb-2">
            Evidence-bound policy prevented an unsafe answer.
          </h2>
          <p className="text-xs text-gray-500">
            The system found related text but could not verify strong, direct support for your question.
          </p>
          <div className="mt-4 flex items-center justify-between">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider">Decision Code</div>
            <div className="text-[10px] font-mono text-red-400">{refusal_code}</div>
          </div>
          {message.reason && (
            <div className="mt-2 text-xs text-gray-400 italic">{message.reason}</div>
          )}
        </div>

        <div className="p-6 border-b border-white/5">
          <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-3">Decision Trace</h3>
          <div className="space-y-2 text-xs text-gray-400">
            <div className="flex items-center justify-between">
              <span>Gate</span>
              <span className="text-red-400">Evidence Strength</span>
            </div>
            <div className="flex items-center justify-between">
              <MetricTooltip
                label="Requirement"
                description="Strict mode requires Grade A unless an exact answer span is verified."
              />
              <span>Grade A (Strong)</span>
            </div>
            {evidence && (
              <div className="flex items-center justify-between">
                <MetricTooltip
                  label="Best Grade"
                  description="Final evidence grade computed from verification, retrieval score, margin, and overlap."
                />
                <span>Grade {evidence.evidence_grade}</span>
              </div>
            )}
            {evidence?.verifier_model && (
              <div className="flex items-center justify-between">
                <MetricTooltip
                  label="LLM Verification"
                  description="Checks for an exact answer span in the retrieved text. VERIFIED means explicit support."
                />
                <span>{evidence.verdict} ({evidence.verifier_model})</span>
              </div>
            )}
            {evidence && (
              <>
                <div className="flex items-center justify-between">
                  <MetricTooltip
                    label="Semantic Rank"
                    description="Azure semantic reranker score (0-4). Higher means stronger semantic relevance."
                  />
                  <span>{evidence.reranker_score ?? "N/A"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <MetricTooltip
                    label="Top RRF Score"
                    description="Reciprocal Rank Fusion across vector and keyword retrieval. Higher means stronger agreement."
                  />
                  <span>{evidence.top_rrf_score}</span>
                </div>
                <div className="flex items-center justify-between">
                  <MetricTooltip
                    label="Overlap Score"
                    description="Lexical overlap between the question and the evidence span. Exact tokens only."
                  />
                  <span>{evidence.overlap_score}</span>
                </div>
                <div className="flex items-center justify-between">
                  <MetricTooltip
                    label="Support Count"
                    description="Count of chunks above the overlap threshold that reinforce the same answer."
                  />
                  <span>{evidence.support_count}</span>
                </div>
              </>
            )}
          </div>
        </div>

        {debug_candidates?.length ? (
          <div className="p-6 border-b border-white/5">
            <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-4">Top Candidates</h3>
            <div className="space-y-3">
              {debug_candidates.slice(0, 3).map((candidate, idx) => (
                <div key={`${candidate.chunk_id}-${idx}`} className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="flex items-center justify-between text-[10px] text-gray-400">
                    <span className="font-mono">
                      {candidate.doc_name} - Pg {candidate.page_num}
                    </span>
                    <span>{candidate.verifier_verdict}</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] text-gray-500">
                    <div title="Rank-fusion score for this candidate in hybrid retrieval.">
                      RRF: {candidate.rrf_score}
                    </div>
                    <div title="Token overlap between question and candidate snippet.">
                      Overlap: {candidate.overlap_score}
                    </div>
                    <div title="Why this candidate was accepted, rejected, or skipped by verification.">
                      Reason: {candidate.reason}
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-gray-300 italic">
                    "{candidate.snippet}"
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="p-6 flex-1">
          <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-4">What We Found</h3>
          <div className="space-y-4">
            {citations?.map((citation, idx) => (
              <div key={idx} className="group relative pl-4 border-l-2 border-white/10">
                <div className="absolute -left-[5px] top-0 w-2 h-2 rounded-full bg-black border border-white/10"></div>
                <div className="text-[10px] text-blue-400 mb-1 font-mono">
                  {citation.doc_name} › Pg {citation.page_num}
                </div>
                <p className="text-xs text-gray-300 leading-relaxed italic opacity-80">
                   {citation.highlighted_text ? (
                      <span dangerouslySetInnerHTML={{ __html: `"${citation.highlighted_text}"` }} />
                   ) : (
                      <span>"{citation.snippet}"</span>
                   )}
                </p>
              </div>
            ))}
            {!citations?.length && (
              <div className="text-xs text-gray-600 italic">
                No citation-ready evidence met the threshold.
              </div>
            )}
          </div>
        </div>

        <div className="p-4 border-t border-white/5 bg-black/20 text-[10px] text-gray-600">
          <div className="font-mono">Policy: Evidence-bound, refusal on weak support</div>
          {version_snapshot && (
            <div className="mt-2 space-y-1 text-gray-500">
              <div>Prompt: {version_snapshot.prompt_version}</div>
              <div>Retrieval: {version_snapshot.retrieval_version}</div>
              <div>Model: {version_snapshot.model_id}</div>
              <div>Parser: {version_snapshot.parser_mode}</div>
              <div>Snapshot: {version_snapshot.docs_snapshot_id}</div>
            </div>
          )}
          <div className="mt-2 text-gray-500">
            Tip: ask a narrower question or upload a more specific document.
          </div>
        </div>
      </div>
    );
  }

  if (!message.evidence && !message.citations) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-gray-600 p-8 text-center border-l border-white/5 bg-white/[0.02]">
        <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h3 className="text-sm font-display font-medium text-gray-400">No Evidence Available</h3>
        <p className="text-xs text-gray-600 mt-2 max-w-[240px]">
          This response did not return citations or a verified evidence chain.
        </p>
        {message.refusal_code && (
          <div className="mt-4 text-[10px] font-mono uppercase tracking-wide text-red-400">
            {message.refusal_code}
          </div>
        )}
        {message.reason && (
          <div className="mt-2 text-xs text-gray-500 italic max-w-[240px]">
            {message.reason}
          </div>
        )}
      </div>
    );
  }

  const { evidence, citations, refusal_code, version_snapshot, debug_candidates } = message;

  return (
    <div className="h-full overflow-y-auto border-l border-white/5 bg-white/[0.02] flex flex-col font-sans">
      <div className="p-6 border-b border-white/5">
        <h2 className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-4">System Rigor</h2>
        
        {/* Status Status */}
        <div className="flex items-center justify-between mb-6">
          <div>
             <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Status</div>
             <div className={`text-sm font-medium ${refusal_code ? "text-red-400" : "text-green-400"}`}>
                {refusal_code ? "REFUSED" : "ANSWERED"}
             </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Request ID</div>
            <div className="text-[10px] font-mono text-gray-400">{message.request_id?.slice(0, 8) || "N/A"}</div>
          </div>
        </div>

        {/* Confidence Section */}
        {evidence && (
            <div className="bg-white/5 rounded-lg p-4 mb-6 border border-white/5">
                <div className="flex justify-between items-end mb-2">
                    <MetricTooltip
                      label="Confidence"
                      description="Evidence strength grade derived from verification, retrieval scores, and overlap."
                    />
                    <span className={`text-xl font-display font-bold ${
                        evidence.evidence_grade === 'A' ? 'text-green-400' :
                        evidence.evidence_grade === 'B' ? 'text-amber-400' : 'text-red-400'
                    }`}>
                        Grade {evidence.evidence_grade}
                    </span>
                </div>
                <div className="w-full bg-white/10 h-1 rounded-full overflow-hidden">
                    <div 
                        className={`h-full ${
                             evidence.evidence_grade === 'A' ? 'bg-green-500' :
                             evidence.evidence_grade === 'B' ? 'bg-amber-500' : 'bg-red-500'
                        }`} 
                        style={{ width: evidence.evidence_grade === 'A' ? '95%' : evidence.evidence_grade === 'B' ? '70%' : '30%' }}
                    ></div>
                </div>
                <div className="mt-3 flex justify-between text-[10px] text-gray-500">
                    <span title="VERIFIED means the model found an explicit answer span in the evidence.">
                      {evidence.verdict}
                    </span>
                    <span title="Number of supporting chunks above the overlap threshold.">
                      {evidence.support_count} Supporting Snippet(s)
                    </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-[10px] text-gray-500">
                    <div title="Azure semantic reranker score (0-4). Higher means stronger semantic relevance.">
                      Semantic: {evidence.reranker_score ?? 0}
                    </div>
                    <div title="Reciprocal Rank Fusion across vector and keyword retrieval.">
                      Top RRF: {evidence.top_rrf_score}
                    </div>
                    <div title="Lexical overlap between the question and evidence span.">
                      Overlap: {evidence.overlap_score}
                    </div>
                    <div title="Count of chunks above the overlap threshold that reinforce the answer.">
                      Support: {evidence.support_count}
                    </div>
                </div>
            </div>
        )}
      </div>

      <div className="p-6 flex-1">
        <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-4">Cited Evidence</h3>
        
        <div className="space-y-4">
            {citations?.map((citation, idx) => (
                <div key={idx} className="group relative pl-4 border-l-2 border-white/10 hover:border-blue-500 transition-colors">
                    <div className="absolute -left-[5px] top-0 w-2 h-2 rounded-full bg-black border border-white/10 group-hover:border-blue-500 transition-colors"></div>
                    <div className="text-[10px] text-blue-400 mb-1 font-mono">
                        {citation.doc_name} • Pg {citation.page_num}
                    </div>
                    <p className="text-xs text-gray-300 leading-relaxed italic opacity-80">
                        {citation.highlighted_text ? (
                            <span dangerouslySetInnerHTML={{ __html: `"${citation.highlighted_text}"` }} />
                        ) : (
                            <span>"{citation.snippet}"</span>
                        )}
                    </p>
                </div>
            ))}
            
            {!citations?.length && (
                <div className="text-xs text-gray-600 italic">
                    No explicit citations available for this response.
                </div>
            )}
        </div>

        {debug_candidates?.length ? (
          <div className="mt-8">
            <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 mb-4">Top Candidates</h3>
            <div className="space-y-3">
              {debug_candidates.slice(0, 3).map((candidate, idx) => (
                <div key={`${candidate.chunk_id}-${idx}`} className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="flex items-center justify-between text-[10px] text-gray-400">
                    <span className="font-mono">
                      {candidate.doc_name} - Pg {candidate.page_num}
                    </span>
                    <span>{candidate.verifier_verdict}</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] text-gray-500">
                    <div title="Rank-fusion score for this candidate in hybrid retrieval.">
                      RRF: {candidate.rrf_score}
                    </div>
                    <div title="Token overlap between question and candidate snippet.">
                      Overlap: {candidate.overlap_score}
                    </div>
                    <div title="Why this candidate was accepted, rejected, or skipped by verification.">
                      Reason: {candidate.reason}
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-gray-300 italic">
                    "{candidate.snippet}"
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
      
      {(evidence || version_snapshot) && (
          <div className="p-4 border-t border-white/5 bg-black/20 text-[10px] text-gray-600 font-mono">
              {evidence && (
                <>
                  <div className="mb-1">SNAPSHOT: {evidence.docs_snapshot_id}</div>
                  <div>INDEX: {evidence.index_version}</div>
                </>
              )}
              {version_snapshot && (
                <div className="mt-2 text-gray-500">
                  <div>PROMPT: {version_snapshot.prompt_version}</div>
                  <div>RETRIEVAL: {version_snapshot.retrieval_version}</div>
                  <div>MODEL: {version_snapshot.model_id}</div>
                  <div>PARSER: {version_snapshot.parser_mode}</div>
                </div>
              )}
          </div>
      )}

      {/* System Rigor / Invariants */}
      <div className="mt-auto p-4 border-t border-white/5 bg-black/40">
        <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase font-bold text-gray-600">System Invariants</span>
            <span className="text-[10px] text-green-500/50 font-mono">v3.1.0</span>
        </div>
        <div className="flex gap-2">
            <span className="px-1.5 py-0.5 bg-green-500/10 border border-green-500/20 text-green-500 text-[9px] font-bold rounded uppercase tracking-wider">
                Evidence-Bound
            </span>
            <span className="px-1.5 py-0.5 bg-blue-500/10 border border-blue-500/20 text-blue-500 text-[9px] font-bold rounded uppercase tracking-wider">
                Hard-Refusal
            </span>
        </div>
      </div>
    </div>
  );
}
