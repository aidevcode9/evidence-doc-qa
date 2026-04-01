import React from "react";
import { Message, RefusalCode } from "@/types";
import { CitationCard } from "./CitationCard";

const REFUSAL_DESCRIPTIONS: Record<RefusalCode, string> = {
  INJECTION_DETECTED: "Query flagged as security risk.",
  LOW_RETRIEVAL_CONFIDENCE: "Information insufficient for reliable answer.",
  NO_SUPPORTING_EVIDENCE: "No relevant information found in documents.",
  PARSE_FAILED: "Document processing error.",
  POLICY_REFUSAL: "Safety policy restriction.",
};

const GRADE_STYLES: Record<string, string> = {
  A: "text-success border-success/30 bg-success/10",
  B: "text-warning border-warning/30 bg-warning/10",
  C: "text-destructive border-destructive/30 bg-destructive/10",
};

export function MessageBubble({ message, onClick, isSelected }: { message: Message; onClick?: () => void; isSelected?: boolean }) {
  const isUser = message.role === "user";
  const isRefusal = !!message.refusal_code;
  const evidence = message.evidence;
  const isSelectable = !isUser && !!onClick;

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4 group`}
      onClick={onClick}
    >
      <div
        className={`relative max-w-[90%] sm:max-w-[80%] rounded-xl px-4 py-3.5 transition-all cursor-default ${isUser
            ? "bg-primary text-primary-foreground"
            : isRefusal
              ? "bg-destructive/5 border border-destructive/20 text-foreground"
              : `bg-card border ${isSelected ? "border-primary/50 shadow-md shadow-primary/5" : "border-border hover:border-border/80"} text-foreground`
          } ${isSelectable ? "cursor-pointer hover:shadow-md active:scale-[0.995]" : ""}`}
      >
        {/* Label */}
        <div className={`text-[10px] font-medium uppercase tracking-widest mb-1.5 ${isUser ? "text-primary-foreground/60" : isRefusal ? "text-destructive" : "text-primary"
          }`}>
          {isUser ? "You" : "Assistant"}
        </div>

        <div className={`text-sm leading-relaxed whitespace-pre-wrap ${isRefusal ? "italic opacity-80" : ""}`}>
          {isRefusal ? message.reason || message.text : message.text}
        </div>

        {/* Refusal details */}
        {message.refusal_code && (
          <div className="mt-3 pt-3 border-t border-destructive/20 flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-destructive animate-pulse"></div>
            <span className="text-[10px] font-mono text-destructive uppercase">
              {message.refusal_code}
            </span>
          </div>
        )}

        {/* Evidence Badge */}
        {evidence && !isRefusal && (
          <div className="mt-3 flex items-center gap-3">
            <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded border ${GRADE_STYLES[evidence.evidence_grade] || "text-muted-foreground border-border"}`}>
              GRADE {evidence.evidence_grade}
            </span>
            {evidence.verdict === "VERIFIED" && (
              <span className="text-[10px] text-success flex items-center gap-1 opacity-80">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                Verified
              </span>
            )}
            {evidence.verdict === "AUTO_VERIFIED" && (
              <span className="text-[10px] text-primary flex items-center gap-1 opacity-80">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 12h16M12 4v16" /></svg>
                Auto-Verified
              </span>
            )}
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border space-y-2">
            {message.citations.map((c, idx) => (
              <CitationCard key={idx} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
