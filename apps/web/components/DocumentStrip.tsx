"use client";

import React, { useState } from "react";
import { DocSummary } from "@/lib/api";

const MAX_VISIBLE = 5;

type DocumentStripProps = {
  documents: DocSummary[];
  loading: boolean;
};

function StatusDot({ status }: { status: string }) {
  if (status === "ready") {
    return <span className="w-1.5 h-1.5 rounded-full bg-success flex-shrink-0" />;
  }
  if (status === "processing" || status === "queued") {
    return <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse flex-shrink-0" />;
  }
  if (status === "failed") {
    return <span className="w-1.5 h-1.5 rounded-full bg-destructive flex-shrink-0" />;
  }
  return <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground flex-shrink-0" />;
}

export function DocumentStrip({ documents, loading }: DocumentStripProps) {
  const [expanded, setExpanded] = useState(false);

  if (loading) {
    return (
      <div className="h-10 border-b border-border bg-muted/30 flex items-center px-6">
        <span className="text-xs text-muted-foreground animate-pulse">Loading documents...</span>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="h-10 border-b border-border bg-muted/30 flex items-center px-6">
        <span className="text-xs text-muted-foreground">No documents yet. Upload to get started.</span>
      </div>
    );
  }

  const visibleDocs = expanded ? documents : documents.slice(0, MAX_VISIBLE);
  const overflowCount = documents.length - MAX_VISIBLE;

  return (
    <div className={`${expanded ? "min-h-10 flex-wrap py-1.5" : "h-10"} border-b border-border bg-muted/30 flex items-center px-6 gap-2 overflow-hidden`}>
      <span className="text-[10px] text-muted-foreground uppercase tracking-wider flex-shrink-0 mr-1">
        Docs
      </span>
      {visibleDocs.map((doc) => (
        <div
          key={doc.doc_id}
          className="flex items-center gap-1.5 px-3 py-1 bg-secondary rounded-full text-xs text-secondary-foreground whitespace-nowrap"
          title={`${doc.doc_name} (${doc.status})`}
        >
          <StatusDot status={doc.status} />
          <span className="max-w-[150px] truncate">{doc.doc_name}</span>
        </div>
      ))}
      {overflowCount > 0 && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="flex items-center px-3 py-1 bg-primary/10 rounded-full text-xs text-primary whitespace-nowrap hover:bg-primary/20 transition-colors cursor-pointer"
        >
          +{overflowCount} more
        </button>
      )}
      {expanded && overflowCount > 0 && (
        <button
          onClick={() => setExpanded(false)}
          className="flex items-center px-3 py-1 bg-secondary rounded-full text-xs text-muted-foreground whitespace-nowrap hover:bg-secondary/80 transition-colors cursor-pointer"
        >
          Show less
        </button>
      )}
    </div>
  );
}
