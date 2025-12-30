import React from "react";
import { Message } from "@/types";

export function EvidencePanel({ message }: { message: Message | null }) {
  if (!message || message.role === "user" || (!message.evidence && !message.citations)) {
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

  const { evidence, citations, refusal_code } = message;

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
                    <span className="text-xs text-gray-400">Confidence</span>
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
                    <span>{evidence.verdict}</span>
                    <span>{evidence.support_count} Supporting Snippet(s)</span>
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
                        "{citation.snippet}"
                    </p>
                </div>
            ))}
            
            {!citations?.length && (
                <div className="text-xs text-gray-600 italic">
                    No explicit citations available for this response.
                </div>
            )}
        </div>
      </div>
      
      {evidence && (
          <div className="p-4 border-t border-white/5 bg-black/20 text-[10px] text-gray-600 font-mono">
              <div className="mb-1">SNAPSHOT: {evidence.docs_snapshot_id}</div>
              <div>INDEX: {evidence.index_version}</div>
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
