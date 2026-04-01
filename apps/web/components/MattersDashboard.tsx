"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { fetchMatters, createMatter, MatterInfo } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

/* ------------------------------------------------------------------ */
/* Utility: relative time                                              */
/* ------------------------------------------------------------------ */

function timeAgo(dateString: string): string {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  if (Number.isNaN(then)) return "";
  const diffMs = now - then;
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 30) return `${days}d ago`;
  return new Date(dateString).toLocaleDateString();
}

/* ------------------------------------------------------------------ */
/* Utility: slugify                                                    */
/* ------------------------------------------------------------------ */

function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/* ------------------------------------------------------------------ */
/* Sort matters by activity                                            */
/* ------------------------------------------------------------------ */

function sortMatters(matters: MatterInfo[]): MatterInfo[] {
  return [...matters].sort((a, b) => {
    // 1. Matters with recent questions first (by last_question_at DESC)
    if (a.last_question_at && b.last_question_at) {
      return new Date(b.last_question_at).getTime() - new Date(a.last_question_at).getTime();
    }
    if (a.last_question_at && !b.last_question_at) return -1;
    if (!a.last_question_at && b.last_question_at) return 1;

    // 2. Matters with docs but no questions
    if (a.doc_count > 0 && b.doc_count === 0) return -1;
    if (a.doc_count === 0 && b.doc_count > 0) return 1;

    // 3. Newer matters before older ones when both are still empty
    if (a.created_at_utc && b.created_at_utc) {
      return new Date(b.created_at_utc).getTime() - new Date(a.created_at_utc).getTime();
    }

    // 4. By doc_count descending
    return b.doc_count - a.doc_count;
  });
}

/* ------------------------------------------------------------------ */
/* Card status line                                                    */
/* ------------------------------------------------------------------ */

function MatterStatusLine({ matter }: { matter: MatterInfo }) {
  if (matter.doc_count === 0) {
    return (
      <span className="text-xs text-muted-foreground/70">
        Upload documents to get started
      </span>
    );
  }
  if (!matter.last_question_at) {
    return (
      <span className="text-xs text-emerald-600 dark:text-emerald-400">
        Ready &mdash; ask your first question
      </span>
    );
  }
  return (
    <p className="text-xs italic text-muted-foreground truncate">
      {matter.last_question_preview || "..."}
    </p>
  );
}

/* ------------------------------------------------------------------ */
/* Skeleton loader                                                     */
/* ------------------------------------------------------------------ */

function SkeletonCard() {
  return (
    <div className="bg-card border border-border rounded-xl p-5 animate-pulse">
      <div className="h-5 bg-muted rounded w-2/3 mb-3" />
      <div className="h-3 bg-muted rounded w-1/3 mb-2" />
      <div className="h-3 bg-muted rounded w-full" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main component                                                      */
/* ------------------------------------------------------------------ */

export function MattersDashboard() {
  const router = useRouter();
  const [matters, setMatters] = useState<MatterInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  const loadMatters = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchMatters();
      setMatters(sortMatters(data));
    } catch {
      setError("Unable to load matters right now.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMatters();
  }, [loadMatters]);

  const handleCreate = async () => {
    const trimmed = newName.trim();
    if (!trimmed) return;
    const slug = slugify(trimmed);
    if (!slug) return;

    setCreating(true);
    try {
      await createMatter(slug, trimmed);
      setDialogOpen(false);
      setNewName("");
      router.push(`/matters/${slug}`);
    } catch {
      setError("Unable to create that matter.");
    } finally {
      setCreating(false);
    }
  };

  /* ---- Empty state ---- */
  if (!loading && !error && matters.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 px-4">
        <div className="text-center space-y-2">
          <h2 className="text-xl font-serif text-foreground">No matters yet</h2>
          <p className="text-sm text-muted-foreground">
            Create your first matter to start uploading documents and asking questions.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)} size="lg">
          + Create your first matter
        </Button>
        <NewMatterDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          name={newName}
          onNameChange={setNewName}
          onCreate={handleCreate}
          creating={creating}
        />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Title row */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-foreground">My Matters</h2>
        <Button onClick={() => setDialogOpen(true)} size="sm" variant="outline">
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Matter
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
          <button
            onClick={loadMatters}
            className="ml-2 underline underline-offset-2 hover:text-destructive/80"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Cards grid */}
      {!loading && matters.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {matters.map((matter) => (
            <button
              key={matter.matter_id}
              onClick={() => router.push(`/matters/${matter.matter_id}`)}
              className="group text-left bg-card border border-border rounded-xl p-5 hover:border-primary/40 hover:shadow-md hover:shadow-primary/5 transition-all duration-200 cursor-pointer"
            >
              <h3 className="font-serif text-base font-medium text-foreground group-hover:text-primary transition-colors truncate">
                {matter.display_name}
              </h3>

              <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                <span>
                  {matter.doc_count} document{matter.doc_count !== 1 ? "s" : ""}
                </span>
                {matter.last_question_at && (
                  <>
                    <span className="text-border">&middot;</span>
                    <span>{timeAgo(matter.last_question_at)}</span>
                  </>
                )}
              </div>

              <div className="mt-3">
                <MatterStatusLine matter={matter} />
              </div>
            </button>
          ))}
        </div>
      )}

      {/* New matter dialog */}
      <NewMatterDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        name={newName}
        onNameChange={setNewName}
        onCreate={handleCreate}
        creating={creating}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* New Matter Dialog                                                   */
/* ------------------------------------------------------------------ */

function NewMatterDialog({
  open,
  onOpenChange,
  name,
  onNameChange,
  onCreate,
  creating,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
  onNameChange: (name: string) => void;
  onCreate: () => void;
  creating: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Matter</DialogTitle>
          <DialogDescription>
            Give your matter a name. You can rename it later.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onCreate();
          }}
        >
          <Input
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="e.g. Smith v. Jones Deposition"
            autoFocus
          />
          <DialogFooter className="mt-4">
            <Button type="submit" disabled={!name.trim() || creating}>
              {creating ? "Creating..." : "Create Matter"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
