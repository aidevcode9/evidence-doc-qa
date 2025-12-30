import React from "react";
import { Message } from "@/types";
import { CitationCard } from "./CitationCard";

const REFUSAL_DESCRIPTIONS: Record<string, string> = {
  INJECTION_DETECTED: "Query flagged as security risk.",
  LOW_RETRIEVAL_CONFIDENCE: "Information insufficient for reliable answer.",
  NO_SUPPORTING_EVIDENCE: "No relevant information found in documents.",
  PARSE_FAILED: "Document processing error.",
  POLICY_REFUSAL: "Safety policy restriction.",
};

const GRADE_COLORS: Record<string, string> = {
  A: "text-green-400 border-green-400/30 bg-green-400/10",
  B: "text-amber-400 border-amber-400/30 bg-amber-400/10",
  C: "text-red-400 border-red-400/30 bg-red-400/10",
};

export function MessageBubble({ message, onClick, isSelected }: { message: Message; onClick?: () => void; isSelected?: boolean }) {
  const isUser = message.role === "user";
  const isRefusal = !!message.refusal_code;
  const evidence = message.evidence;
  const isSelectable = !isUser && !!onClick;

  return (
    <div 
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-6 group`}
      onClick={onClick}
    >
      <div
        className={`relative max-w-[90%] sm:max-w-[80%] rounded-2xl px-5 py-4 transition-all cursor-default ${
          isUser
            ? "bg-white text-black"
            : isRefusal
            ? "bg-red-950/30 border border-red-500/30 text-red-200"
            : `bg-zinc-900 border ${isSelected ? "border-blue-500/50 shadow-[0_0_15px_rgba(59,130,246,0.1)]" : "border-white/10 hover:border-white/20"} text-gray-300`
        } ${isSelectable ? "cursor-pointer hover:bg-zinc-800/80 active:border-blue-400/60" : ""}`}
      >
        {/* User / Assistant Label */}
        <div className={`text-[10px] font-bold uppercase tracking-widest mb-2 ${
            isUser ? "text-gray-400" : "text-blue-500"
        }`}>
            {isUser ? "You" : "Assistant"}
        </div>

        <div className={`text-sm sm:text-base leading-relaxed whitespace-pre-wrap font-sans ${isRefusal ? "italic opacity-80" : ""}`}>
          {isRefusal ? message.reason || message.text : message.text}
        </div>

        {/* Refusal details */}
        {message.refusal_code && (
          <div className="mt-3 pt-3 border-t border-red-500/20 flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></div>
            <span className="text-[10px] font-mono text-red-400 uppercase">
                {message.refusal_code}
            </span>
          </div>
        )}

        {/* Minimal Evidence Badge */}
        {evidence && !isRefusal && (
          <div className="mt-4 flex items-center gap-3">
             <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded border ${GRADE_COLORS[evidence.evidence_grade] || "text-gray-400 border-gray-700"}`}>
                GRADE {evidence.evidence_grade}
             </span>
             {evidence.verdict === "VERIFIED" && (
                 <span className="text-[10px] text-green-500 flex items-center gap-1 opacity-80">
                     <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg>
                     Verified
                 </span>
             )}
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-4 pt-3 border-t border-white/5 space-y-2">
            {message.citations.map((c, idx) => (
              <CitationCard key={idx} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

