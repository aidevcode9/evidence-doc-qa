import React, { useState, useEffect } from "react";
import { Citation } from "@/types";

interface DocumentViewerProps {
  citation: Citation | null;
  apiUrl: string;
  onClose: () => void;
}

export function DocumentViewer({ citation, apiUrl, onClose }: DocumentViewerProps) {
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

  // Build URL with page fragment for PDF navigation
  const docUrl = `${apiUrl}/v1/docs/${citation.doc_id}/view#page=${citation.page_num}`;

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
      {/* Modal Container */}
      <div className="relative w-[90vw] h-[90vh] max-w-6xl bg-gray-900 rounded-lg border border-white/10 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex-none h-14 px-4 flex items-center justify-between border-b border-white/10 bg-black/50">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-sm font-display font-semibold text-white">
                {citation.doc_name}
              </h2>
              <p className="text-xs text-gray-400">
                Page {citation.page_num} • Citation [{citation.citation_index}]
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Highlight Info */}
            <div className="px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded text-xs text-amber-400">
              <span className="font-medium">Cited:</span>{" "}
              <span className="italic">"{citation.snippet.slice(0, 50)}..."</span>
            </div>

            {/* Open in New Tab */}
            <button
              onClick={handleOpenInNewTab}
              className="p-2 rounded hover:bg-white/10 transition-colors"
              title="Open in new tab"
            >
              <svg
                className="w-4 h-4 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                />
              </svg>
            </button>

            {/* Close Button */}
            <button
              onClick={onClose}
              className="p-2 rounded hover:bg-white/10 transition-colors"
              title="Close"
            >
              <svg
                className="w-5 h-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>

        {/* Document Viewer */}
        <div className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
              <div className="text-center">
                <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-sm text-gray-400">Loading document...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
              <div className="text-center">
                <svg
                  className="w-12 h-12 text-red-500 mx-auto mb-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                <p className="text-sm text-red-400">{error}</p>
                <button
                  onClick={handleOpenInNewTab}
                  className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded transition-colors"
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

        {/* Footer with Citation Details */}
        <div className="flex-none h-12 px-4 flex items-center justify-between border-t border-white/10 bg-black/50 text-xs text-gray-500">
          <div className="flex items-center gap-4">
            <span>
              <strong className="text-gray-400">Doc ID:</strong> {citation.doc_id.slice(0, 8)}...
            </span>
            <span>
              <strong className="text-gray-400">Chunk:</strong> {citation.chunk_id}
            </span>
            <span>
              <strong className="text-gray-400">Chars:</strong> {citation.char_start}-{citation.char_end}
            </span>
          </div>
          <div>
            <strong className="text-gray-400">Score:</strong> {citation.score.toFixed(4)}
          </div>
        </div>
      </div>
    </div>
  );
}
