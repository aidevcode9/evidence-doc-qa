"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { fetchMatters, MatterInfo } from "@/lib/api";
import { Logo } from "@/components/Logo";
import { UserMenu } from "@/components/UserMenu";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function MyMattersPage() {
  const router = useRouter();
  const [matters, setMatters] = useState<MatterInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // localStorage migration: if a matter was previously selected, redirect to it
    const savedMatterId = localStorage.getItem("docqa_matter");
    if (savedMatterId) {
      localStorage.removeItem("docqa_matter");
      router.replace(`/matters/${encodeURIComponent(savedMatterId)}`);
      return;
    }

    fetchMatters()
      .then((list) => {
        setMatters(list);
      })
      .catch(() => {
        setError("Unable to load matters. Please ensure the backend is running.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [router]);

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground font-sans">
      {/* Header */}
      <header className="flex-none h-14 border-b border-border flex items-center justify-between px-3 sm:px-4 lg:px-6 bg-background/80 backdrop-blur-md z-30">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <Logo size={28} />
          <div className="hidden sm:block">
            <h1 className="text-sm font-semibold tracking-tight leading-none text-foreground">
              Evidence Bound
            </h1>
          </div>
        </div>
        <div className="flex items-center gap-1.5 sm:gap-2">
          <ThemeToggle />
          <UserMenu />
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto w-full">
        <h2 className="text-2xl font-semibold tracking-tight text-foreground font-display mb-6">
          My Matters
        </h2>

        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {!loading && !error && matters.length === 0 && (
          <div className="rounded-lg border border-border bg-card p-12 text-center">
            <p className="text-muted-foreground text-sm">
              No matters yet. Create a new matter to get started.
            </p>
          </div>
        )}

        {!loading && !error && matters.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {matters.map((matter) => (
              <Link
                key={matter.matter_id}
                href={`/matters/${encodeURIComponent(matter.matter_id)}`}
                className="group rounded-lg border border-border bg-card p-4 hover:border-primary/40 hover:shadow-sm transition-all"
              >
                <h3 className="text-sm font-medium text-foreground group-hover:text-primary transition-colors truncate">
                  {matter.display_name}
                </h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  {matter.doc_count} {matter.doc_count === 1 ? "document" : "documents"}
                </p>
                {matter.last_question_preview && (
                  <p className="mt-2 text-xs text-muted-foreground/70 truncate">
                    {matter.last_question_preview}
                  </p>
                )}
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
