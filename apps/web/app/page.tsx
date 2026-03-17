"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Message, Citation } from "@/types";
import { IngestionZone } from "@/components/IngestionZone";
import { ChatInterface } from "@/components/ChatInterface";
import { EvidencePanel } from "@/components/EvidencePanel";
import { DocumentViewer } from "@/components/DocumentViewer";
import { UserMenu } from "@/components/UserMenu";
import { Toast } from "@/components/Toast";
import { CasePicker } from "@/components/CasePicker";
import { DocumentStrip } from "@/components/DocumentStrip";
import {
  getAuthHeaders,
  getApiUrl,
  setCurrentMatter,
  fetchMatters,
  fetchMatterDocs,
  MatterInfo,
  DocSummary,
} from "@/lib/api";

export default function DocQAPage() {
  const [docsSnapshotId, setDocsSnapshotId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<{ name: string; email: string } | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [toast, setToast] = useState<{ message: string; variant: "info" | "warning" | "error" } | null>(null);
  const [selectedMatter, setSelectedMatter] = useState<MatterInfo | null>(null);
  const [documents, setDocuments] = useState<DocSummary[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [pinnedDocId, setPinnedDocId] = useState<string | null>(null);
  const [pinnedDocName, setPinnedDocName] = useState<string | null>(null);

  const handleToast = useCallback((message: string, variant: "info" | "warning" | "error" = "info") => {
    setToast({ message, variant });
  }, []);

  const handleToastClose = useCallback(() => setToast(null), []);

  const handleCitationClick = (citation: Citation) => {
    setSelectedCitation(citation);
  };

  const handleCloseViewer = () => {
    setSelectedCitation(null);
  };

  const loadDocsForMatter = useCallback(async (matterId: string) => {
    setDocsLoading(true);
    try {
      const docs = await fetchMatterDocs(matterId);
      setDocuments(docs);
    } catch {
      setDocuments([]);
    } finally {
      setDocsLoading(false);
    }
  }, []);

  const handleMatterChange = useCallback(
    (matter: MatterInfo) => {
      setCurrentMatter(matter.matter_id);
      setSelectedMatter(matter);
      if (matter.latest_snapshot_id) {
        setDocsSnapshotId(matter.latest_snapshot_id);
      } else {
        setDocsSnapshotId("");
      }
      setMessages([]);
      // Generate new session for this case
      const newSession = crypto.randomUUID();
      localStorage.setItem("docqa_session", newSession);
      setSessionId(newSession);
      loadDocsForMatter(matter.matter_id);
    },
    [loadDocsForMatter]
  );

  const handleNewCase = useCallback((slug: string) => {
    const newMatter: MatterInfo = {
      matter_id: slug,
      display_name: slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      doc_count: 0,
      latest_snapshot_id: null,
    };
    setCurrentMatter(slug);
    setSelectedMatter(newMatter);
    setDocsSnapshotId("");
    setDocuments([]);
    setMessages([]);
    const newSession = crypto.randomUUID();
    localStorage.setItem("docqa_session", newSession);
    setSessionId(newSession);
  }, []);

  useEffect(() => {
    // Generate or restore session ID for export functionality (FR-032)
    let storedSession = localStorage.getItem("docqa_session");
    if (!storedSession) {
      storedSession = crypto.randomUUID();
      localStorage.setItem("docqa_session", storedSession);
    }
    setSessionId(storedSession);

    const storedUser = localStorage.getItem("docqa_user");
    if (storedUser) {
      try {
        const parsed = JSON.parse(storedUser) as { name?: string; email?: string };
        if (parsed.name && parsed.email) {
          setUserProfile({ name: parsed.name, email: parsed.email });
        }
      } catch {
        // Ignore invalid storage.
      }
    }

    // Load matters and auto-select saved matter (don't auto-select first)
    const savedMatterId = localStorage.getItem("docqa_matter");
    fetchMatters()
      .then((matterList) => {
        if (matterList.length === 0) return;
        if (savedMatterId) {
          const target = matterList.find((m) => m.matter_id === savedMatterId);
          if (target) handleMatterChange(target);
        }
        // If no saved matter, don't auto-select — let user pick
      })
      .catch(() => {
        // Backend not available — leave empty
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
    // Refresh doc list and matters (doc count changed)
    if (selectedMatter) {
      loadDocsForMatter(selectedMatter.matter_id);
    }
  };

  const handleAsk = async (question: string, overrideDocId?: string) => {
    const userMsg: Message = { id: crypto.randomUUID(), role: "user", text: question };
    setMessages((prev) => [...prev, userMsg]);
    setIsAsking(true);

    const effectiveDocId = overrideDocId ?? pinnedDocId ?? undefined;

    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      };
      if (sessionId) headers["X-DocQA-Session"] = sessionId;
      if (userProfile?.email) headers["X-DocQA-User-Email"] = userProfile.email;
      if (userProfile?.name) headers["X-DocQA-User-Name"] = userProfile.name;

      const res = await fetch(`${getApiUrl()}/v1/ask`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          question,
          docs_snapshot_id: docsSnapshotId || undefined,
          doc_id: effectiveDocId,
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
        debug_candidates: data.debug_candidates,
        refusal_code: data.refusal_code,
        reason: data.reason,
        request_id: data.request_id,
        version_snapshot: data.version_snapshot,
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

  const handleCandidateSelect = async (docId: string, docName: string) => {
    setPinnedDocId(docId);
    setPinnedDocName(docName);
    // Re-run the last user question scoped to this document
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (lastUserMsg) {
      await handleAsk(lastUserMsg.text, docId);
    }
  };

  const handleUnpin = () => {
    setPinnedDocId(null);
    setPinnedDocName(null);
  };

  const selectedMessage = messages.find((m) => m.id === selectedMessageId) || null;

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-black text-white selection:bg-blue-500/30 font-sans">
      {/* Header */}
      <header className="flex-none h-16 border-b border-white/10 flex items-center justify-between px-6 bg-black/50 backdrop-blur-md z-30">
        <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
                <span className="font-display font-bold text-black text-xl">E</span>
            </div>
            <div>
                <h1 className="text-lg font-display font-bold tracking-tight leading-none">
                    Evidence Bound <span className="opacity-40 font-normal text-sm ml-1">v3.1</span>
                </h1>
            </div>
            <CasePicker
              onMatterChange={handleMatterChange}
              onNewCase={handleNewCase}
              activeMatterId={selectedMatter?.matter_id || null}
              onToast={handleToast}
            />
        </div>
        <div className="flex items-center gap-3">
          <IngestionZone onUploadSuccess={handleUploadSuccess} onToast={handleToast} />
          <UserMenu />
        </div>
      </header>

      {/* Document strip below header */}
      <DocumentStrip documents={documents} loading={docsLoading} />

      {/* Pinned document indicator */}
      {pinnedDocId && (
        <div className="flex-none h-8 border-b border-blue-500/20 bg-blue-600/10 flex items-center px-6 gap-2">
          <svg className="w-3 h-3 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10 2a1 1 0 011 1v1.323l3.954 1.582 1.599-.8a1 1 0 01.894 1.79l-1.233.616 1.738 5.42a1 1 0 01-.285 1.05A3.989 3.989 0 0115 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.715-5.349L11 6.477V16h2a1 1 0 110 2H7a1 1 0 110-2h2V6.477L6.237 7.582l1.715 5.349a1 1 0 01-.285 1.05A3.989 3.989 0 015 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.738-5.42-1.233-.617a1 1 0 01.894-1.789l1.599.799L9 4.323V3a1 1 0 011-1z" />
          </svg>
          <span className="text-xs text-blue-400">Pinned: {pinnedDocName}</span>
          <button
            onClick={handleUnpin}
            className="ml-auto text-[10px] text-gray-500 hover:text-white px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 transition-colors cursor-pointer"
          >
            Unpin
          </button>
        </div>
      )}

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
            <EvidencePanel
              message={selectedMessage}
              onCitationClick={handleCitationClick}
              onCandidateSelect={handleCandidateSelect}
              sessionId={sessionId}
            />
        </div>
      </main>

      {/* Document Viewer Modal (FR-031) */}
      {selectedCitation && (
        <DocumentViewer
          citation={selectedCitation}
          onClose={handleCloseViewer}
        />
      )}

      {/* Toast notifications */}
      {toast && (
        <Toast
          message={toast.message}
          variant={toast.variant}
          onClose={handleToastClose}
        />
      )}
    </div>
  );
}
