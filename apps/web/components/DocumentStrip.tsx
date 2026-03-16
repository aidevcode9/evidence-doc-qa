"use client";

import React from "react";
import { DocSummary } from "@/lib/api";

type DocumentStripProps = {
  documents: DocSummary[];
  loading: boolean;
};

function StatusDot({ status }: { status: string }) {
  if (status === "ready") {
    return <span className="w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />;
  }
  if (status === "processing" || status === "queued") {
    return <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse flex-shrink-0" />;
  }
  if (status === "failed") {
    return <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />;
  }
  return <span className="w-1.5 h-1.5 rounded-full bg-gray-500 flex-shrink-0" />;
}

export function DocumentStrip({ documents, loading }: DocumentStripProps) {
  if (loading) {
    return (
      <div className="h-10 border-b border-white/5 bg-black/30 flex items-center px-6">
        <span className="text-xs text-gray-500 animate-pulse">Loading documents...</span>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="h-10 border-b border-white/5 bg-black/30 flex items-center px-6">
        <span className="text-xs text-gray-500">No documents yet. Upload to get started.</span>
      </div>
    );
  }

  return (
    <div className="h-10 border-b border-white/5 bg-black/30 flex items-center px-6 gap-2 overflow-x-auto scrollbar-hide">
      <span className="text-[10px] text-gray-600 uppercase tracking-wider flex-shrink-0 mr-1">
        Docs
      </span>
      {documents.map((doc) => (
        <div
          key={doc.doc_id}
          className="flex items-center gap-1.5 px-3 py-1 bg-white/5 rounded-full text-xs text-gray-400 whitespace-nowrap"
          title={`${doc.doc_name} (${doc.status})`}
        >
          <StatusDot status={doc.status} />
          <span className="max-w-[150px] truncate">{doc.doc_name}</span>
        </div>
      ))}
    </div>
  );
}
