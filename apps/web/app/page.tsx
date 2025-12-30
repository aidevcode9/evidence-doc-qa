"use client";

import React, { useState, useEffect } from "react";
import { Message } from "@/types";
import { IngestionZone } from "@/components/IngestionZone";
import { ChatInterface } from "@/components/ChatInterface";
import { EvidencePanel } from "@/components/EvidencePanel";

export default function DocQAPage() {
  const [docsSnapshotId, setDocsSnapshotId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleUploadSuccess = (snapshotId: string, fileName: string) => {
    setDocsSnapshotId(snapshotId);
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        text: `Document "${fileName}" uploaded and indexed. Snapshot: ${snapshotId}.`,
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
        text: data.answer_text || "The system could not provide an answer.",
        citations: data.citations,
        evidence: data.evidence,
        refusal_code: data.refusal_code,
        reason: data.reason,
        request_id: data.request_id,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setSelectedMessageId(assistantMsg.id); // Auto-select latest
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

  const selectedMessage = messages.find((m) => m.id === selectedMessageId) || null;

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-black text-white selection:bg-blue-500/30 font-sans">
      {/* Header */}
      <header className="flex-none h-16 border-b border-white/10 flex items-center justify-between px-6 bg-black/50 backdrop-blur-md z-10">
        <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
                <span className="font-display font-bold text-black text-xl">D</span>
            </div>
            <div>
                <h1 className="text-lg font-display font-bold tracking-tight leading-none">
                    DocQ&A <span className="opacity-40 font-normal text-sm ml-1">v3.1</span>
                </h1>
            </div>
        </div>
        <IngestionZone onUploadSuccess={handleUploadSuccess} apiUrl={API_URL} />
      </header>

      {/* Main Grid */}
      <main className="flex-1 flex flex-col md:flex-row overflow-hidden relative">
        {/* Background Grid Pattern */}
        <div className="absolute inset-0 bg-grid-pattern opacity-20 pointer-events-none" />

        {/* Chat Column */}
        <div className="flex-1 flex flex-col relative z-0 min-w-0">
          <ChatInterface
            messages={messages}
            onAsk={handleAsk}
            isAsking={isAsking}
            isReady={!!docsSnapshotId}
            selectedMessageId={selectedMessageId}
            onMessageSelect={(m) => setSelectedMessageId(m.id)}
          />
        </div>

        {/* Evidence Column */}
        <div className="flex-none w-full md:w-[400px] lg:w-[450px] bg-black/40 backdrop-blur-xl border-t md:border-t-0 border-white/10 md:border-l z-10 h-[40vh] md:h-full">
            <EvidencePanel message={selectedMessage} />
        </div>
      </main>
    </div>
  );
}