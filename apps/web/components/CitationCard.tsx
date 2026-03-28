import React from "react";
import { Citation } from "@/types";

export function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div className="bg-muted/50 p-3 rounded-lg border border-border text-sm hover:bg-muted transition-colors">
      <div className="flex justify-between text-xs font-medium text-primary mb-1">
        <span>{citation.doc_name} - Page {citation.page_num}</span>
        <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Source</span>
      </div>
      <p className="italic text-muted-foreground text-xs">&quot;...{citation.snippet}...&quot;</p>
    </div>
  );
}
