import React from "react";
import { Citation } from "@/types";

export function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div className="bg-black/20 p-3 rounded-lg border border-white/5 text-sm hover:bg-black/30 transition-colors">
      <div className="flex justify-between text-xs font-semibold text-blue-400 mb-1">
        <span>{citation.doc_name} - Page {citation.page_num}</span>
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Source</span>
      </div>
      <p className="italic text-gray-400 text-xs">"...{citation.snippet}..."</p>
    </div>
  );
}
