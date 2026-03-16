"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import { apiUpload, apiRequest, fetchCapabilities, type ServerCapabilities } from "@/lib/api";

type IngestionStatus = "idle" | "uploading" | "queued" | "processing" | "ready" | "failed";

type StatusResponse = {
  doc_id: string;
  status: string;
  doc_name: string;
  docs_snapshot_id?: string;
  error_message?: string | null;
  retry_count?: number;
};

type IngestionZoneProps = {
  onUploadSuccess: (snapshotId: string, fileName: string) => void;
};

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 150; // 5 minutes max

export function IngestionZone({ onUploadSuccess }: IngestionZoneProps) {
  const [status, setStatus] = useState<IngestionStatus>("idle");
  const [docId, setDocId] = useState<string | null>(null);
  const [docName, setDocName] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [retryCount, setRetryCount] = useState(0);
  const [capabilities, setCapabilities] = useState<ServerCapabilities | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollCountRef = useRef(0);

  useEffect(() => {
    fetchCapabilities()
      .then(setCapabilities)
      .catch((err) => console.error("Failed to fetch capabilities:", err));
  }, []);

  // Poll for status updates when queued or processing
  useEffect(() => {
    if (!docId || (status !== "queued" && status !== "processing")) return;

    const interval = setInterval(async () => {
      pollCountRef.current += 1;
      if (pollCountRef.current > MAX_POLL_ATTEMPTS) {
        setStatus("failed");
        setErrorMessage("Processing timed out. Please retry.");
        clearInterval(interval);
        return;
      }

      try {
        const data = await apiRequest<StatusResponse>(`/v1/docs/${docId}/status`);
        if (data.status === "ready") {
          setStatus("ready");
          if (data.docs_snapshot_id) {
            onUploadSuccess(data.docs_snapshot_id, docName);
          }
          clearInterval(interval);
        } else if (data.status === "failed") {
          setStatus("failed");
          setErrorMessage(data.error_message || "Processing failed.");
          setRetryCount(data.retry_count || 0);
          clearInterval(interval);
        } else if (data.status === "processing") {
          setStatus("processing");
        }
      } catch {
        // Transient error — keep polling
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [docId, status, docName, onUploadSuccess]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setStatus("uploading");
    setDocName(file.name);
    setErrorMessage("");
    pollCountRef.current = 0;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await apiUpload("/v1/docs/upload", formData);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(err.detail || "Upload failed");
      }
      const data = await res.json();

      if (data.status === "queued") {
        setDocId(data.doc_id);
        setStatus("queued");
      } else {
        // Legacy sync response (status not present = already done)
        onUploadSuccess(data.docs_snapshot_id, file.name);
        setStatus("idle");
      }
    } catch (err) {
      console.error(err);
      setStatus("failed");
      setErrorMessage(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleRetry = useCallback(async () => {
    if (!docId) return;

    setStatus("queued");
    setErrorMessage("");
    pollCountRef.current = 0;

    try {
      await apiRequest(`/v1/docs/${docId}/retry`, { method: "POST" });
    } catch (err) {
      console.error(err);
      setStatus("failed");
      setErrorMessage("Retry failed. Please try uploading again.");
    }
  }, [docId]);

  const handleDismiss = useCallback(() => {
    setStatus("idle");
    setDocId(null);
    setDocName("");
    setErrorMessage("");
    setRetryCount(0);
  }, []);

  const isPdfOnly = capabilities?.parser_provider === "pypdf";
  const acceptFormats = isPdfOnly ? ".pdf" : ".pdf,.png,.jpg,.jpeg,.tiff,.tif";
  const buttonText = isPdfOnly ? "Upload PDF" : "Upload PDF/Image";

  // Status badge rendering
  if (status === "queued" || status === "processing") {
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-xl px-4 py-2">
          <span className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-400"></span>
          <span className="text-sm text-blue-300">
            {status === "queued" ? "Queued" : "Processing"}
          </span>
          <span className="text-xs text-blue-400/60 truncate max-w-[120px]">{docName}</span>
        </div>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">
          <svg className="w-3.5 h-3.5 text-red-400 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          <span className="text-xs text-red-300 truncate max-w-[140px]" title={errorMessage}>
            {errorMessage.length > 30 ? errorMessage.slice(0, 30) + "..." : errorMessage}
          </span>
        </div>
        {docId && (
          <button
            onClick={handleRetry}
            className="text-xs text-blue-400 hover:text-blue-300 underline underline-offset-2 cursor-pointer"
          >
            Retry
          </button>
        )}
        <button
          onClick={handleDismiss}
          className="text-xs text-gray-500 hover:text-gray-400 cursor-pointer"
        >
          Dismiss
        </button>
      </div>
    );
  }

  if (status === "ready") {
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 bg-green-500/10 border border-green-500/20 rounded-xl px-4 py-2">
          <svg className="w-3.5 h-3.5 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span className="text-sm text-green-300">Ready</span>
          <span className="text-xs text-green-400/60 truncate max-w-[120px]">{docName}</span>
        </div>
        <button
          onClick={handleDismiss}
          className="text-xs text-gray-500 hover:text-gray-400 cursor-pointer"
        >
          Dismiss
        </button>
      </div>
    );
  }

  // Default idle state — upload button
  return (
    <div className="flex items-center gap-4">
      <input
        type="file"
        accept={acceptFormats}
        onChange={handleUpload}
        ref={fileInputRef}
        className="hidden"
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={status === "uploading"}
        className="bg-white text-black hover:bg-gray-200 px-5 py-2.5 rounded-xl text-sm font-bold tracking-wide transition-all shadow-[0_0_20px_rgba(255,255,255,0.1)] disabled:opacity-50 flex items-center gap-2"
      >
        {status === "uploading" ? (
          <span className="animate-spin rounded-full h-3 w-3 border-b-2 border-black"></span>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
        )}
        {status === "uploading" ? "Uploading..." : buttonText}
      </button>
    </div>
  );
}
