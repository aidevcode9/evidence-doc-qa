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
        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-all shadow-md disabled:opacity-50 flex items-center gap-2"
      >
        {isUploading ? (
          <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
        ) : null}
        {isUploading ? "Processing..." : "Upload PDF"}
      </button>
    </div>
  );
}
