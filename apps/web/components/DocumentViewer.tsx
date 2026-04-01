import React, { useState, useEffect } from "react";
import { Citation } from "@/types";
import { getCurrentMatter } from "@/lib/api";

interface DocumentViewerProps {
  citation: Citation | null;
  onClose: () => void;
}

export function DocumentViewer({ citation, onClose }: DocumentViewerProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (citation) {
      setLoading(true);
      setError(null);
    }
  }, [citation]);

  if (!citation) {
    return null;
  }

  const matterId = getCurrentMatter();
  const docUrl = `/api/docs/${citation.doc_id}/view?matter_id=${encodeURIComponent(matterId)}#page=${citation.page_num}`;

  const handleIframeLoad = () => {
    setLoading(false);
  };

  const handleIframeError = () => {
    setLoading(false);
    setError("Failed to load document");
  };

  const handleOpenInNewTab = () => {
    window.open(docUrl, "_blank");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="relative w-[90vw] h-[90vh] max-w-6xl bg-card rounded-xl border border-border flex flex-col overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex-none h-14 px-4 flex items-center justify-between border-b border-border bg-card">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                {citation.doc_name}
              </h2>
              <p className="text-xs text-muted-foreground">
                Page {citation.page_num}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="px-3 py-1.5 bg-primary/10 border border-primary/20 rounded-lg text-xs text-primary">
              <span className="font-medium">Cited:</span>{" "}
              <span className="italic">&quot;{citation.snippet.slice(0, 50)}...&quot;</span>
            </div>

            <button
              onClick={handleOpenInNewTab}
              className="p-2 rounded-lg hover:bg-muted transition-colors"
              title="Open in new tab"
            >
              <svg className="w-4 h-4 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </button>

            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-muted transition-colors"
              title="Close"
            >
              <svg className="w-5 h-5 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Document Viewer */}
        <div className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-card">
              <div className="text-center">
                <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">Loading document...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-card">
              <div className="text-center">
                <svg className="w-12 h-12 text-destructive mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p className="text-sm text-destructive">{error}</p>
                <button
                  onClick={handleOpenInNewTab}
                  className="mt-4 px-4 py-2 bg-primary hover:bg-primary/90 text-primary-foreground text-sm rounded-lg transition-colors"
                >
                  Open in New Tab
                </button>
              </div>
            </div>
          )}

          <iframe
            src={docUrl}
            className="w-full h-full bg-white"
            onLoad={handleIframeLoad}
            onError={handleIframeError}
            title={`${citation.doc_name} - Page ${citation.page_num}`}
          />
        </div>

        {/* Footer */}
        <div className="flex-none h-10 px-4 flex items-center justify-between border-t border-border bg-muted/30 text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <span>
              <strong className="text-foreground/70">Doc ID:</strong> {citation.doc_id.slice(0, 8)}...
            </span>
            <span>
              <strong className="text-foreground/70">Chunk:</strong> {citation.chunk_id}
            </span>
            <span>
              <strong className="text-foreground/70">Chars:</strong> {citation.char_start}-{citation.char_end}
            </span>
          </div>
          <div>
            <strong className="text-foreground/70">Score:</strong> {citation.score.toFixed(4)}
          </div>
        </div>
      </div>
    </div>
  );
}
