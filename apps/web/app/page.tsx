"use client";

import React, { useState } from "react";
import { Message } from "@/types";
import { IngestionZone } from "@/components/IngestionZone";
import { ChatInterface } from "@/components/ChatInterface";

export default function DocQAPage() {
  const [docsSnapshotId, setDocsSnapshotId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAsking, setIsAsking] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleUploadSuccess = (snapshotId: string, fileName: string) => {
    setDocsSnapshotId(snapshotId);
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        text: `Document "${fileName}" uploaded and indexed. Snapshot: ${snapshotId}. You can now ask questions about it.`,
      },
    ]);
  };

  const handleAsk = async (question: string) => {
    const userMsg: Message = { id: crypto.randomUUID(), role: "user", text: question };
    setMessages((prev) => [...prev, userMsg]);
    setIsAsking(true);

    try {
      const res = await fetch(`${API_URL}/v1/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          docs_snapshot_id: docsSnapshotId || undefined,
        }),
      });

      if (!res.ok) throw new Error("Request failed");
      const data = await res.json();

      const assistantMsg: Message = {
        id: data.request_id || crypto.randomUUID(),
        role: "assistant",
        text: data.answer_text || data.reason || "I could not find an answer.",
        citations: data.citations,
        refusal_code: data.refusal_code,
        request_id: data.request_id,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: "Error connecting to the API. Please ensure the backend is running.",
        },
      ]);
    } finally {
      setIsAsking(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center p-4 sm:p-8 font-sans text-gray-900">
      <header className="w-full max-w-4xl flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">
            DocQ&A <span className="text-blue-600">v3.1</span>
          </h1>
          <p className="text-gray-500 text-sm font-medium">Evidence-Bound Document Assistant</p>
        </div>
        <IngestionZone onUploadSuccess={handleUploadSuccess} apiUrl={API_URL} />
      </header>

      <main className="w-full max-w-4xl bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden h-[75vh] border border-gray-100">
        <ChatInterface
          messages={messages}
          onAsk={handleAsk}
          isAsking={isAsking}
          isReady={!!docsSnapshotId}
        />
      </main>

      <footer className="mt-8 text-center space-y-3">
        <div className="flex justify-center gap-6">
          <div className="text-center">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Invariants</p>
            <div className="flex gap-2">
              <span className="px-2 py-0.5 bg-green-50 text-green-700 rounded text-[9px] font-bold border border-green-100">EVIDENCE-BOUND</span>
              <span className="px-2 py-0.5 bg-red-50 text-red-700 rounded text-[9px] font-bold border border-red-100">HARD-REFUSAL</span>
            </div>
          </div>
        </div>
        {docsSnapshotId && (
          <div className="inline-block bg-blue-50 text-blue-700 px-4 py-1.5 rounded-full text-[10px] font-mono border border-blue-100 shadow-sm">
            <span className="opacity-50 mr-2">ACTIVE SNAPSHOT:</span> {docsSnapshotId}
          </div>
        )}
      </footer>
    </div>
  );
}
