"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchMatter, setCurrentMatter } from "@/lib/api";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UserMenu } from "@/components/UserMenu";
import { MattersDashboard } from "@/components/MattersDashboard";

export default function DashboardPage() {
  const router = useRouter();
  const [migrated, setMigrated] = useState(false);

  /* Task 4: localStorage migration — redirect existing single-matter users */
  useEffect(() => {
    const savedMatter = localStorage.getItem("docqa_matter");
    if (savedMatter) {
      fetchMatter(savedMatter)
        .then(() => {
          router.replace(`/matters/${savedMatter}`);
        })
        .catch(() => {
          localStorage.removeItem("docqa_matter");
          setCurrentMatter("");
          setMigrated(true);
        });
      return;
    }
    setMigrated(true);
  }, [router]);

  if (!migrated) {
    return (
      <div className="h-screen flex items-center justify-center bg-background text-foreground">
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card/70 px-4 py-3 shadow-sm">
          <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-muted-foreground">Loading your matters...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-background text-foreground font-sans">
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
      <MattersDashboard />
    </div>
  );
}
