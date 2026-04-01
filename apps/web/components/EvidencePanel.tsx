import React from "react";
import { Message, Citation, DebugCandidate } from "@/types";
import { getAuthHeaders, getApiUrl } from "@/lib/api";

const MetricTooltip = ({ label, description }: { label: string; description: string }) => (
  <span className="flex items-center gap-2">
    <span>{label}</span>
    <span
      className="text-[10px] text-muted-foreground border border-border rounded-full w-4 h-4 flex items-center justify-center cursor-help"
      title={description}
    >
      i
    </span>
  </span>
);

const MAX_HIGHLIGHT_LEN = 2000;

const sanitizeHighlight = (text: string) => {
  const safe = text.replace(/<(?!\/?em\b)[^>]*>/gi, "");
  if (safe.length <= MAX_HIGHLIGHT_LEN) {
    return safe;
  }
  return `${safe.slice(0, MAX_HIGHLIGHT_LEN)}...`;
};

const renderHighlightedText = (text: string): React.ReactNode[] => {
  const sanitized = sanitizeHighlight(text);
  const parts: React.ReactNode[] = [];
  const regex = /<em>(.*?)<\/em>/gi;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let partIndex = 0;

  while ((match = regex.exec(sanitized)) !== null) {
    if (match.index > lastIndex) {
      parts.push(
        <span key={`t-${partIndex++}`}>{sanitized.slice(lastIndex, match.index)}</span>
      );
    }
    parts.push(
      <em key={`e-${partIndex++}`} className="text-primary not-italic font-medium">
        {match[1]}
      </em>
    );
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < sanitized.length) {
    parts.push(<span key={`t-${partIndex++}`}>{sanitized.slice(lastIndex)}</span>);
  }

  return parts.length ? parts : [sanitized];
};

function CandidateCard({
  candidate,
  idx,
  onSelect,
}: {
  candidate: DebugCandidate;
  idx: number;
  onSelect?: (docId: string, docName: string) => void;
}) {
  return (
    <button
      key={`${candidate.chunk_id}-${idx}`}
      className="rounded-lg border border-border bg-card p-3 w-full text-left hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer"
      onClick={() => onSelect?.(candidate.doc_id, candidate.doc_name)}
      title="Click to re-query scoped to this document"
    >
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span className="font-mono">
          {candidate.doc_name} - Pg {candidate.page_num}
        </span>
        <span>{candidate.verifier_verdict}</span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] text-muted-foreground/70">
        {candidate.azure_search_score !== null && candidate.azure_search_score !== undefined ? (
          <div title="Azure @search.score for this candidate from hybrid retrieval.">
            Azure Hybrid: {candidate.azure_search_score}
          </div>
        ) : (
          <div title="Rank-fusion score for this candidate in hybrid retrieval.">
            RRF: {candidate.rrf_score}
          </div>
        )}
        {candidate.azure_reranker_score !== null && candidate.azure_reranker_score !== undefined && (
          <div title="Azure semantic reranker score (0-4).">
            Reranker: {candidate.azure_reranker_score}
          </div>
        )}
        <div title="Token overlap between question and candidate snippet.">
          Overlap: {candidate.overlap_score}
        </div>
        <div title="Why this candidate was accepted, rejected, or skipped.">
          Reason: {candidate.reason}
        </div>
      </div>
      <div className="mt-2 text-xs text-muted-foreground italic">
        &quot;{candidate.snippet}&quot;
      </div>
      <div className="mt-1.5 text-[9px] text-primary/60 uppercase tracking-wider">
        Click to search this document
      </div>
    </button>
  );
}

interface EvidencePanelProps {
  message: Message | null;
  onCitationClick?: (citation: Citation) => void;
  onCandidateSelect?: (docId: string, docName: string) => void;
  sessionId?: string | null;
}

const ExportButtons = ({ sessionId }: { sessionId?: string | null }) => {
  const [isExporting, setIsExporting] = React.useState<"pdf" | "docx" | null>(null);

  if (!sessionId) return null;

  const handleExport = async (format: "pdf" | "docx") => {
    if (isExporting) return;

    setIsExporting(format);
    try {
      const url = `${getApiUrl()}/v1/sessions/${sessionId}/export?format=${format}`;
      const response = await fetch(url, {
        method: "GET",
        headers: {
          ...getAuthHeaders(),
          "X-DocQA-Session": sessionId,
        },
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Export failed" }));
        throw new Error(error.detail || "Export failed");
      }

      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = `qa-export-${sessionId.slice(0, 8)}.${format}`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^";\n]+)"?/);
        if (match) filename = match[1];
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      console.error("Export failed:", error);
      alert(error instanceof Error ? error.message : "Export failed");
    } finally {
      setIsExporting(null);
    }
  };

  return (
    <div className="flex gap-2 mt-3">
      <button
        onClick={() => handleExport("pdf")}
        disabled={isExporting !== null}
        className="flex-1 px-3 py-2 bg-primary/10 border border-primary/20 hover:bg-primary/20 text-primary text-xs font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        title="Export Q&A session as PDF"
      >
        {isExporting === "pdf" ? (
          <span className="inline-block w-3.5 h-3.5 mr-1.5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        ) : (
          <svg className="w-3.5 h-3.5 inline-block mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        )}
        {isExporting === "pdf" ? "Exporting..." : "PDF"}
      </button>
      <button
        onClick={() => handleExport("docx")}
        disabled={isExporting !== null}
        className="flex-1 px-3 py-2 bg-success/10 border border-success/20 hover:bg-success/20 text-success text-xs font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        title="Export Q&A session as DOCX"
      >
        {isExporting === "docx" ? (
          <span className="inline-block w-3.5 h-3.5 mr-1.5 border-2 border-success border-t-transparent rounded-full animate-spin" />
        ) : (
          <svg className="w-3.5 h-3.5 inline-block mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        )}
        {isExporting === "docx" ? "Exporting..." : "DOCX"}
      </button>
    </div>
  );
};

export function EvidencePanel({ message, onCitationClick, onCandidateSelect, sessionId }: EvidencePanelProps) {
  if (!message) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-8 text-center">
        <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-muted-foreground/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-foreground/70">Evidence Monitor</h3>
        <p className="text-xs text-muted-foreground mt-2 max-w-[200px]">
          Select a response to view its verified evidence chain and confidence score.
        </p>
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-8 text-center">
        <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-muted-foreground/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-foreground/70">Evidence Monitor</h3>
        <p className="text-xs text-muted-foreground mt-2 max-w-[200px]">
          Select an assistant response to review its evidence and citations.
        </p>
      </div>
    );
  }

  if (message.refusal_code) {
    const { evidence, citations, refusal_code, version_snapshot, debug_candidates } = message;
    const azureSearchScore = evidence?.azure_search_score ?? null;
    const semanticScore =
      evidence?.azure_reranker_score ?? (evidence?.reranker_score ? evidence.reranker_score : null);
    const hasAzureScore = azureSearchScore !== null && azureSearchScore !== undefined;
    return (
      <div className="h-full overflow-y-auto flex flex-col">
        <div className="p-5 border-b border-border">
          <div className="text-[10px] font-medium uppercase tracking-widest text-destructive mb-2">
            Refusal Is The Correct Answer
          </div>
          <h2 className="text-sm font-semibold text-foreground mb-2">
            Evidence-bound policy prevented an unsafe answer.
          </h2>
          <p className="text-xs text-muted-foreground">
            The system found related text but could not verify strong, direct support for your question.
          </p>
          <div className="mt-4 flex items-center justify-between">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Decision Code</div>
            <div className="text-[10px] font-mono text-destructive">{refusal_code}</div>
          </div>
          {message.reason && (
            <div className="mt-2 text-xs text-muted-foreground italic">{message.reason}</div>
          )}
        </div>

        <div className="p-5 border-b border-border">
          <h3 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-3">Decision Trace</h3>
          <div className="space-y-2 text-xs text-muted-foreground">
            <div className="flex items-center justify-between">
              <span>Gate</span>
              <span className="text-destructive">Evidence Strength</span>
            </div>
            <div className="flex items-center justify-between">
              <MetricTooltip label="Requirement" description="Strict mode requires Grade A unless an exact answer span is verified." />
              <span>Grade A (Strong)</span>
            </div>
            {evidence && (
              <div className="flex items-center justify-between">
                <MetricTooltip label="Best Grade" description="Final evidence grade computed from verification, retrieval score, margin, and overlap." />
                <span>Grade {evidence.evidence_grade}</span>
              </div>
            )}
            {evidence?.verifier_model && (
              <div className="flex items-center justify-between">
                <MetricTooltip label="LLM Verification" description="Checks for an exact answer span in the retrieved text." />
                <span>{evidence.verdict} ({evidence.verifier_model})</span>
              </div>
            )}
            {evidence && (
              <>
                <div className="flex items-center justify-between">
                  <MetricTooltip label="Semantic Rank" description="Azure semantic reranker score (0-4)." />
                  <span>{semanticScore ?? "N/A"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <MetricTooltip label={hasAzureScore ? "Azure Hybrid Score" : "Top RRF Score"} description={hasAzureScore ? "Azure @search.score from hybrid retrieval." : "Reciprocal Rank Fusion across vector and keyword retrieval."} />
                  <span>{hasAzureScore ? azureSearchScore : evidence.top_rrf_score}</span>
                </div>
                <div className="flex items-center justify-between">
                  <MetricTooltip label="Overlap Score" description="Lexical overlap between the question and the evidence span." />
                  <span>{evidence.overlap_score}</span>
                </div>
                <div className="flex items-center justify-between">
                  <MetricTooltip label="Support Count" description="Count of chunks above the overlap threshold." />
                  <span>{evidence.support_count}</span>
                </div>
              </>
            )}
          </div>
        </div>

        {debug_candidates?.length ? (
          <div className="p-5 border-b border-border">
            <h3 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">Top Candidates</h3>
            <div className="space-y-3">
              {debug_candidates.slice(0, 3).map((candidate, idx) => (
                <CandidateCard key={`${candidate.chunk_id}-${idx}`} candidate={candidate} idx={idx} onSelect={onCandidateSelect} />
              ))}
            </div>
          </div>
        ) : null}

        <div className="p-5 flex-1">
          <h3 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">What We Found</h3>
          <div className="space-y-4">
            {citations?.map((citation, idx) => (
              <button
                key={idx}
                onClick={() => onCitationClick?.(citation)}
                className="group relative pl-4 border-l-2 border-border hover:border-primary transition-colors text-left w-full cursor-pointer"
                title="Click to view source document"
              >
                <div className="absolute -left-[5px] top-0 w-2 h-2 rounded-full bg-background border border-border group-hover:border-primary transition-colors"></div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-primary font-mono">
                    [{citation.citation_index}] {citation.doc_name} - Pg {citation.page_num}
                  </span>
                  <span className="text-[10px] text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                    View Source
                  </span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed italic opacity-80">
                   {citation.highlighted_text ? (
                      <span>&quot;{renderHighlightedText(citation.highlighted_text)}&quot;</span>
                   ) : (
                      <span>&quot;{citation.snippet}&quot;</span>
                   )}
                </p>
              </button>
            ))}
            {!citations?.length && (
              <div className="text-xs text-muted-foreground italic">
                No citation-ready evidence met the threshold.
              </div>
            )}
          </div>
        </div>

        <div className="p-4 border-t border-border bg-muted/30 text-[10px] text-muted-foreground">
          <div className="font-mono">Policy: Evidence-bound, refusal on weak support</div>
          {version_snapshot && (
            <div className="mt-2 space-y-1 text-muted-foreground/70">
              <div>Prompt: {version_snapshot.prompt_version}</div>
              {version_snapshot.verifier_prompt_version && (
                <div>Verifier: {version_snapshot.verifier_prompt_version}</div>
              )}
              <div>Retrieval: {version_snapshot.retrieval_version}</div>
              <div>Model: {version_snapshot.model_id}</div>
              <div>Parser: {version_snapshot.parser_mode}</div>
              <div>Snapshot: {version_snapshot.docs_snapshot_id}</div>
            </div>
          )}
          <div className="mt-2 text-muted-foreground/70">
            Tip: ask a narrower question or upload a more specific document.
          </div>
        </div>
      </div>
    );
  }

  if (!message.evidence && !message.citations) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-muted-foreground p-8 text-center">
        <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-muted-foreground/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-foreground/70">No Evidence Available</h3>
        <p className="text-xs text-muted-foreground mt-2 max-w-[240px]">
          This response did not return citations or a verified evidence chain.
        </p>
        {message.refusal_code && (
          <div className="mt-4 text-[10px] font-mono uppercase tracking-wide text-destructive">
            {message.refusal_code}
          </div>
        )}
        {message.reason && (
          <div className="mt-2 text-xs text-muted-foreground italic max-w-[240px]">
            {message.reason}
          </div>
        )}
      </div>
    );
  }

  const { evidence, citations, refusal_code, version_snapshot, debug_candidates } = message;
  const azureSearchScore = evidence?.azure_search_score ?? null;
  const semanticScore =
    evidence?.azure_reranker_score ?? (evidence?.reranker_score ? evidence.reranker_score : null);
  const hasAzureScore = azureSearchScore !== null && azureSearchScore !== undefined;

  return (
    <div className="h-full overflow-y-auto flex flex-col">
      <div className="p-5 border-b border-border">
        <h2 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">System Rigor</h2>

        <div className="flex items-center justify-between mb-5">
          <div>
             <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Status</div>
             <div className={`text-sm font-medium ${refusal_code ? "text-destructive" : "text-success"}`}>
                {refusal_code ? "REFUSED" : "ANSWERED"}
             </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Request ID</div>
            <div className="text-[10px] font-mono text-muted-foreground">{message.request_id?.slice(0, 8) || "N/A"}</div>
          </div>
        </div>

        {evidence && (
            <div className="bg-muted/50 rounded-xl p-4 mb-4 border border-border">
                <div className="flex justify-between items-end mb-2">
                    <MetricTooltip label="Confidence" description="Evidence strength grade derived from verification, retrieval scores, and overlap." />
                    <span className={`text-xl font-semibold ${
                        evidence.evidence_grade === 'A' ? 'text-success' :
                        evidence.evidence_grade === 'B' ? 'text-warning' : 'text-destructive'
                    }`}>
                        Grade {evidence.evidence_grade}
                    </span>
                </div>
                <div className="w-full bg-border h-1.5 rounded-full overflow-hidden">
                    <div
                        className={`h-full rounded-full transition-all ${
                             evidence.evidence_grade === 'A' ? 'bg-success' :
                             evidence.evidence_grade === 'B' ? 'bg-warning' : 'bg-destructive'
                        }`}
                        style={{ width: evidence.evidence_grade === 'A' ? '95%' : evidence.evidence_grade === 'B' ? '70%' : '30%' }}
                    ></div>
                </div>
                <div className="mt-3 flex justify-between text-[10px] text-muted-foreground">
                    <span
                      title={
                        evidence.verdict === "AUTO_VERIFIED"
                          ? "AUTO_VERIFIED means the top candidate cleared semantic reranker and overlap thresholds, so the LLM verifier was skipped."
                          : "VERIFIED means the model found an explicit answer span in the evidence."
                      }
                    >
                      {evidence.verdict}
                    </span>
                    <span title="Number of supporting chunks above the overlap threshold.">
                      {evidence.support_count} Supporting Snippet(s)
                    </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-[10px] text-muted-foreground/70">
                    <div title="Azure semantic reranker score (0-4).">
                      Semantic: {semanticScore ?? "N/A"}
                    </div>
                    <div title={hasAzureScore ? "Azure @search.score from hybrid retrieval." : "Reciprocal Rank Fusion."}>
                      {hasAzureScore ? "Azure Hybrid" : "Top RRF"}:{" "}
                      {hasAzureScore ? azureSearchScore : evidence.top_rrf_score}
                    </div>
                    <div title="Lexical overlap between the question and evidence span.">
                      Overlap: {evidence.overlap_score}
                    </div>
                    <div title="Count of chunks above the overlap threshold.">
                      Support: {evidence.support_count}
                    </div>
                </div>
            </div>
        )}
      </div>

      <div className="p-5 flex-1">
        <h3 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">Cited Evidence</h3>

        <div className="space-y-4">
            {citations?.map((citation, idx) => (
                <button
                    key={idx}
                    onClick={() => onCitationClick?.(citation)}
                    className="group relative pl-4 border-l-2 border-border hover:border-primary transition-colors text-left w-full cursor-pointer"
                    title="Click to view source document"
                >
                    <div className="absolute -left-[5px] top-0 w-2 h-2 rounded-full bg-background border border-border group-hover:border-primary transition-colors"></div>
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-primary font-mono">
                            [{citation.citation_index}] {citation.doc_name} - Pg {citation.page_num}
                        </span>
                        <span className="text-[10px] text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                            View Source
                        </span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed italic opacity-80">
                        {citation.highlighted_text ? (
                            <span>&quot;{renderHighlightedText(citation.highlighted_text)}&quot;</span>
                        ) : (
                            <span>&quot;{citation.snippet}&quot;</span>
                        )}
                    </p>
                </button>
            ))}

            {!citations?.length && (
                <div className="text-xs text-muted-foreground italic">
                    No explicit citations available for this response.
                </div>
            )}
        </div>

        {debug_candidates?.length ? (
          <div className="mt-8">
            <h3 className="text-xs font-medium uppercase tracking-widest text-muted-foreground mb-4">Top Candidates</h3>
            <div className="space-y-3">
              {debug_candidates.slice(0, 3).map((candidate, idx) => (
                <CandidateCard key={`${candidate.chunk_id}-${idx}`} candidate={candidate} idx={idx} onSelect={onCandidateSelect} />
              ))}
            </div>
          </div>
        ) : null}
      </div>

      {(evidence || version_snapshot) && (
          <div className="p-4 border-t border-border bg-muted/30 text-[10px] text-muted-foreground font-mono">
              {evidence && (
                <>
                  <div className="mb-1">SNAPSHOT: {evidence.docs_snapshot_id}</div>
                  <div>INDEX: {evidence.index_version}</div>
                </>
              )}
              {version_snapshot && (
                <div className="mt-2 text-muted-foreground/70">
                  <div>PROMPT: {version_snapshot.prompt_version}</div>
                  {version_snapshot.verifier_prompt_version && (
                    <div>VERIFIER: {version_snapshot.verifier_prompt_version}</div>
                  )}
                  <div>RETRIEVAL: {version_snapshot.retrieval_version}</div>
                  <div>MODEL: {version_snapshot.model_id}</div>
                  <div>PARSER: {version_snapshot.parser_mode}</div>
                </div>
              )}
          </div>
      )}

      {sessionId && (
        <div className="p-4 border-t border-border bg-muted/20">
          <div className="text-[10px] uppercase font-medium text-muted-foreground mb-1">Export Session</div>
          <ExportButtons sessionId={sessionId} />
        </div>
      )}

      <div className="mt-auto p-4 border-t border-border bg-muted/30">
        <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase font-medium text-muted-foreground">System Invariants</span>
            <span className="text-[10px] text-muted-foreground/50 font-mono">v3.1.0</span>
        </div>
        <div className="flex gap-2">
            <span className="px-1.5 py-0.5 bg-success/10 border border-success/20 text-success text-[9px] font-medium rounded uppercase tracking-wider">
                Evidence-Bound
            </span>
            <span className="px-1.5 py-0.5 bg-primary/10 border border-primary/20 text-primary text-[9px] font-medium rounded uppercase tracking-wider">
                Hard-Refusal
            </span>
        </div>
      </div>
    </div>
  );
}
