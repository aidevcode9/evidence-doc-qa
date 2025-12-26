import React from "react";
import { Citation } from "@/types";

export function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div className="bg-white p-3 rounded-lg border border-gray-200 text-sm shadow-sm">
      <div className="flex justify-between text-xs font-semibold text-blue-700 mb-1">
        <span>{citation.doc_name} • Page {citation.page_num}</span>
        <span>{Math.round(citation.score * 100)}% Match</span>
      </div>
      <p className="italic text-gray-600">"...{citation.snippet}..."</p>
    </div>
  );
}
