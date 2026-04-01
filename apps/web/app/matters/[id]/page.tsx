"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Message, Citation } from "@/types";
import { IngestionZone } from "@/components/IngestionZone";
import { ChatInterface } from "@/components/ChatInterface";
import { EvidencePanel } from "@/components/EvidencePanel";
import { DocumentViewer } from "@/components/DocumentViewer";
import { UserMenu } from "@/components/UserMenu";
import { Toast } from "@/components/Toast";
import { DocumentStrip } from "@/components/DocumentStrip";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Logo } from "@/components/Logo";
import {
  apiRequest,
  fetchMatter,
  fetchMatterDocs,
  getAuthHeaders,
  getMatterSessionId,
  MatterInfo,
  DocSummary,
  renameMatter,
  setCurrentMatter,
  setMatterSessionId,
} from "@/lib/api";

type AskResponsePayload = {
  answer_text?: string;
  citations?: Citation[];
  debug_candidates?: Message["debug_candidates"];
  evidence?: Message["evidence"];
  reason?: string | null;
  refusal_code?: string | null;
  request_id?: string;
  version_snapshot?: Message["version_snapshot"];
};

export default function MatterChatPage() {
  const params = useParams<{ id: string }>();
  const matterId = params.id;

  const [docsSnapshotId, setDocsSnapshotId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<{ name: string; email: string } | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [toast, setToast] = useState<{ message: string; variant: "info" | "warning" | "error" } | null>(null);
  const [matterDisplayName, setMatterDisplayName] = useState<string>("");
  const [matterLoading, setMatterLoading] = useState(true);
  const [matterError, setMatterError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocSummary[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [pinnedDocId, setPinnedDocId] = useState<string | null>(null);
  const [pinnedDocName, setPinnedDocName] = useState<string | null>(null);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [isSavingName, setIsSavingName] = useState(false);

  const handleToast = useCallback(
    (message: string, variant: "info" | "warning" | "error" = "info") => {
      setToast({ message, variant });
    },
    []
  );

  const handleToastClose = useCallback(() => setToast(null), []);

  const handleCitationClick = (citation: Citation) => {
    setSelectedCitation(citation);
  };

  const handleCloseViewer = () => {
    setSelectedCitation(null);
  };

  const loadDocsForMatter = useCallback(async (id: string) => {
    setDocsLoading(true);
    try {
      const docs = await fetchMatterDocs(id);
      setDocuments(docs);
    } catch {
      setDocuments([]);
    } finally {
      setDocsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!matterId) return;

    setCurrentMatter(matterId);
    setMatterLoading(true);
    setMatterError(null);
    setMessages([]);
    setPinnedDocId(null);
    setPinnedDocName(null);
    setSelectedMessageId(null);
    setIsRenaming(false);
    setRenameValue("");

    let storedSession = getMatterSessionId(matterId);
    if (!storedSession) {
      storedSession = crypto.randomUUID();
      setMatterSessionId(matterId, storedSession);
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

    fetchMatter(matterId)
      .then((matter: MatterInfo) => {
        setMatterDisplayName(matter.display_name);
        setRenameValue(matter.display_name);
        setDocsSnapshotId(matter.latest_snapshot_id || "");
        setMatterError(null);
      })
      .catch((error) => {
        setMatterDisplayName("");
        setDocsSnapshotId("");
        setMatterError(
          error instanceof Error
            ? error.message
            : "We couldn't load this matter right now."
        );
      })
      .finally(() => {
        setMatterLoading(false);
      });

    loadDocsForMatter(matterId);
  }, [matterId, loadDocsForMatter]);

  const handleUploadSuccess = (snapshotId: string, fileName: string) => {
    setDocsSnapshotId(snapshotId);
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        text: `Document "${fileName}" uploaded and indexed.`,
      },
    ]);
    loadDocsForMatter(matterId);
  };

  const handleAsk = async (question: string, overrideDocId?: string) => {
    const userMsg: Message = { id: crypto.randomUUID(), role: "user", text: question };
    setMessages((prev) => [...prev, userMsg]);
    setIsAsking(true);

    const effectiveDocId = overrideDocId ?? pinnedDocId ?? undefined;

    try {
      const data = await apiRequest<AskResponsePayload>("/v1/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders(),
          ...(sessionId ? { "X-DocQA-Session": sessionId } : {}),
          ...(userProfile?.email ? { "X-DocQA-User-Email": userProfile.email } : {}),
          ...(userProfile?.name ? { "X-DocQA-User-Name": userProfile.name } : {}),
        },
        body: JSON.stringify({
          question,
          docs_snapshot_id: docsSnapshotId || undefined,
          doc_id: effectiveDocId,
        }),
      });

      const assistantMsg: Message = {
        id: data.request_id || crypto.randomUUID(),
        role: "assistant",
        text: data.answer_text || "The system could not provide an answer.",
        citations: data.citations,
        evidence: data.evidence,
        debug_candidates: data.debug_candidates,
        refusal_code: data.refusal_code || undefined,
        reason: data.reason || undefined,
        request_id: data.request_id,
        version_snapshot: data.version_snapshot,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setSelectedMessageId(assistantMsg.id);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: "We couldn't reach the evidence service. Please try again.",
        },
      ]);
    } finally {
      setIsAsking(false);
    }
  };

  const handleCandidateSelect = async (docId: string, docName: string) => {
    setPinnedDocId(docId);
    setPinnedDocName(docName);
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (lastUserMsg) {
      await handleAsk(lastUserMsg.text, docId);
    }
  };

  const handleUnpin = () => {
    setPinnedDocId(null);
    setPinnedDocName(null);
  };

  const handleRenameSave = async () => {
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === matterDisplayName) {
      setIsRenaming(false);
      setRenameValue(matterDisplayName);
      return;
    }

    setIsSavingName(true);
    try {
      await renameMatter(matterId, trimmed);
      setMatterDisplayName(trimmed);
      setRenameValue(trimmed);
      setIsRenaming(false);
      handleToast("Matter renamed.", "info");
    } catch {
      handleToast("Unable to rename this matter.", "error");
    } finally {
      setIsSavingName(false);
    }
  };

  const selectedMessage = messages.find((m) => m.id === selectedMessageId) || null;
  const showMatterUnavailable = !matterLoading && !!matterError;

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-background text-foreground selection:bg-primary/20 font-sans">
      <header className="flex-none h-14 border-b border-border flex items-center justify-between px-3 sm:px-4 lg:px-6 bg-background/80 backdrop-blur-md z-30">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <Logo size={28} />
          <div className="hidden sm:block">
            <h1 className="text-sm font-semibold tracking-tight leading-none text-foreground">
              Evidence Bound
            </h1>
          </div>
          <div className="w-px h-6 bg-border hidden sm:block" />
          <Link
            href="/"
            className="flex items-center gap-1 text-xs sm:text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            <span className="hidden sm:inline">My Matters</span>
          </Link>
          <div className="w-px h-6 bg-border" />
          {matterLoading ? (
            <span className="text-sm text-muted-foreground">Loading matter...</span>
          ) : isRenaming ? (
            <div className="flex items-center gap-2 min-w-0">
              <input
                value={renameValue}
                onChange={(event) => setRenameValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void handleRenameSave();
                  if (event.key === "Escape") {
                    setRenameValue(matterDisplayName);
                    setIsRenaming(false);
                  }
                }}
                className="h-8 min-w-0 max-w-[220px] rounded-md border border-border bg-background px-2 text-sm text-foreground outline-none focus:border-primary"
                aria-label="Rename matter"
                disabled={isSavingName}
              />
              <button
                onClick={() => void handleRenameSave()}
                className="text-xs text-primary hover:text-primary/80"
                disabled={isSavingName}
              >
                {isSavingName ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => {
                  setRenameValue(matterDisplayName);
                  setIsRenaming(false);
                }}
                className="text-xs text-muted-foreground hover:text-foreground"
                disabled={isSavingName}
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm font-medium text-foreground truncate max-w-[140px] sm:max-w-[240px]">
                {showMatterUnavailable ? "Matter unavailable" : matterDisplayName}
              </span>
              {!showMatterUnavailable && (
                <button
                  onClick={() => setIsRenaming(true)}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  title="Rename matter"
                >
                  Rename
                </button>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1.5 sm:gap-2">
          {!showMatterUnavailable && !matterLoading && (
            <>
              <IngestionZone onUploadSuccess={handleUploadSuccess} onToast={handleToast} />
              <div className="w-px h-6 bg-border hidden sm:block" />
            </>
          )}
          <ThemeToggle />
          <UserMenu />
        </div>
      </header>

      {!showMatterUnavailable && !matterLoading && (
        <>
          <DocumentStrip documents={documents} loading={docsLoading} />

          {pinnedDocId && (
            <div className="flex-none h-8 border-b border-primary/20 bg-primary/5 flex items-center px-6 gap-2">
              <svg className="w-3 h-3 text-primary" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 2a1 1 0 011 1v1.323l3.954 1.582 1.599-.8a1 1 0 01.894 1.79l-1.233.616 1.738 5.42a1 1 0 01-.285 1.05A3.989 3.989 0 0115 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.715-5.349L11 6.477V16h2a1 1 0 110 2H7a1 1 0 110-2h2V6.477L6.237 7.582l1.715 5.349a1 1 0 01-.285 1.05A3.989 3.989 0 015 15a3.989 3.989 0 01-2.667-1.019 1 1 0 01-.285-1.05l1.738-5.42-1.233-.617a1 1 0 01.894-1.789l1.599.799L9 4.323V3a1 1 0 011-1z" />
              </svg>
              <span className="text-xs text-primary">Pinned: {pinnedDocName}</span>
              <button
                onClick={handleUnpin}
                className="ml-auto text-[10px] text-muted-foreground hover:text-foreground px-2 py-0.5 rounded bg-secondary hover:bg-secondary/80 transition-colors cursor-pointer"
              >
                Unpin
              </button>
            </div>
          )}
        </>
      )}

      {matterLoading ? (
        <main className="flex-1 flex items-center justify-center px-6">
          <div className="flex items-center gap-3 rounded-xl border border-border bg-card/70 px-4 py-3 shadow-sm">
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-muted-foreground">Loading matter workspace...</span>
          </div>
        </main>
      ) : showMatterUnavailable ? (
        <main className="flex-1 flex items-center justify-center px-6">
          <div className="max-w-md rounded-2xl border border-border bg-card/70 p-6 text-center shadow-sm">
            <h2 className="text-lg font-semibold text-foreground">
              We couldn&apos;t open this matter
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {matterError || "This matter may no longer exist, or you may not have access to it."}
            </p>
            <div className="mt-5 flex items-center justify-center gap-3">
              <Link
                href="/"
                className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Back to matters
              </Link>
              <button
                onClick={() => window.location.reload()}
                className="rounded-lg border border-border px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        </main>
      ) : (
        <main className="flex-1 flex flex-col md:flex-row overflow-hidden relative">
          <div className="absolute inset-0 bg-grid-pattern opacity-30 pointer-events-none" />

          <div className="flex-1 flex flex-col relative z-0 min-w-0">
            <ChatInterface
              messages={messages}
              onAsk={handleAsk}
              isAsking={isAsking}
              isReady={!!docsSnapshotId}
              selectedMessageId={selectedMessageId}
              onMessageSelect={(message) => setSelectedMessageId(message.id)}
            />
          </div>

          <div className={`flex-none w-full md:w-[380px] lg:w-[420px] bg-card/50 backdrop-blur-xl border-t md:border-t-0 border-border md:border-l z-10 md:h-full ${selectedMessage ? "h-[40vh]" : "hidden md:block"}`}>
            <EvidencePanel
              message={selectedMessage}
              onCitationClick={handleCitationClick}
              onCandidateSelect={handleCandidateSelect}
              sessionId={sessionId}
            />
          </div>
        </main>
      )}

      {selectedCitation && (
        <DocumentViewer citation={selectedCitation} onClose={handleCloseViewer} />
      )}

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
