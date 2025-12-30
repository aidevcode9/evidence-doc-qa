"use client";

import React, { useRef, useState } from "react";

type IngestionZoneProps = {
  onUploadSuccess: (snapshotId: string, fileName: string) => void;
  apiUrl: string;
};

export function IngestionZone({ onUploadSuccess, apiUrl }: IngestionZoneProps) {
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${apiUrl}/v1/docs/upload`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed");
      const data = await res.json();
      onUploadSuccess(data.docs_snapshot_id, file.name);
    } catch (err) {
      console.error(err);
      alert("Failed to upload document.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="flex items-center gap-4">
      <input
        type="file"
        accept=".pdf"
        onChange={handleUpload}
        ref={fileInputRef}
        className="hidden"
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={isUploading}
        className="bg-white text-black hover:bg-gray-200 px-5 py-2.5 rounded-xl text-sm font-bold tracking-wide transition-all shadow-[0_0_20px_rgba(255,255,255,0.1)] disabled:opacity-50 flex items-center gap-2"
      >
        {isUploading ? (
          <span className="animate-spin rounded-full h-3 w-3 border-b-2 border-black"></span>
        ) : (
           <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
        )}
        {isUploading ? "Indexing..." : "Upload PDF"}
      </button>
    </div>
  );
}
