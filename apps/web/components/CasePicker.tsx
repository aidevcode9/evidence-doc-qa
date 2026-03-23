"use client";

import React, { useState, useEffect, useRef } from "react";
import { createMatter, fetchMatters, renameMatter, MatterInfo } from "@/lib/api";

type CasePickerProps = {
  onMatterChange: (matter: MatterInfo) => void;
  onNewCase: (caseName: string) => void;
  activeMatterId: string | null;
  onToast?: (message: string, variant: "info" | "warning" | "error") => void;
};

function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function CasePicker({
  onMatterChange,
  onNewCase,
  activeMatterId,
  onToast,
}: CasePickerProps) {
  const [matters, setMatters] = useState<MatterInfo[]>([]);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState("");
  const [renameName, setRenameName] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  const loadMatters = async () => {
    try {
      const data = await fetchMatters();
      setMatters(data);
    } catch {
      // Silently fail — user will see empty picker
    }
  };

  useEffect(() => {
    loadMatters();
  }, []);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setCreating(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Focus input when creating
  useEffect(() => {
    if (creating && inputRef.current) {
      inputRef.current.focus();
    }
  }, [creating]);

  // Focus input when renaming
  useEffect(() => {
    if (renaming && renameInputRef.current) {
      renameInputRef.current.focus();
    }
  }, [renaming]);

  const active = matters.find((m) => m.matter_id === activeMatterId);

  const handleSelect = (matter: MatterInfo) => {
    onMatterChange(matter);
    setOpen(false);
  };

  const handleRename = async () => {
    const trimmed = renameName.trim();
    if (!trimmed || !active) return;
    try {
      await renameMatter(active.matter_id, trimmed);
      // Update local state
      setMatters((prev) =>
        prev.map((m) =>
          m.matter_id === active.matter_id ? { ...m, display_name: trimmed } : m
        )
      );
      onMatterChange({ ...active, display_name: trimmed });
    } catch {
      onToast?.("Failed to rename case", "error");
    }
    setRenaming(false);
    setRenameName("");
  };

  const handleNewCase = async () => {
    const trimmed = newName.trim();
    if (!trimmed) return;
    const slug = slugify(trimmed);
    if (!slug) return;
    try {
      await createMatter(slug, trimmed);
    } catch {
      // Best-effort — matter row will be created on first upload if this fails
    }
    onNewCase(slug);
    setNewName("");
    setCreating(false);
    setOpen(false);
    // Reload matters after a short delay to include new case
    setTimeout(loadMatters, 500);
  };

  return (
    <div className="relative" ref={ref}>
      {/* Trigger */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm hover:bg-white/10 transition-colors cursor-pointer"
      >
        <svg
          className="w-4 h-4 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
          />
        </svg>
        <span className="text-gray-200 max-w-[160px] truncate">
          {active?.display_name || "Select Case"}
        </span>
        {active && (
          <span className="text-[10px] text-gray-500 bg-white/5 rounded-full px-2 py-0.5">
            {active.doc_count} doc{active.doc_count !== 1 ? "s" : ""}
          </span>
        )}
        <svg
          className={`w-3 h-3 text-gray-500 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute left-0 top-full mt-1 w-72 bg-zinc-900/95 backdrop-blur-md border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden">
          {/* Matter list */}
          <div className="max-h-64 overflow-y-auto py-1">
            {matters.length === 0 && (
              <div className="px-4 py-3 text-sm text-gray-500">
                No cases found. Upload a document to create one.
              </div>
            )}
            {matters.map((matter) => (
              <button
                key={matter.matter_id}
                onClick={() => handleSelect(matter)}
                className={`w-full text-left px-4 py-2.5 hover:bg-white/5 rounded-lg cursor-pointer flex items-center justify-between transition-colors ${
                  matter.matter_id === activeMatterId
                    ? "bg-white/5 border-l-2 border-blue-500"
                    : ""
                }`}
              >
                <span className="text-sm text-gray-200 truncate">
                  {matter.display_name}
                </span>
                <span className="text-[10px] text-gray-500 bg-white/5 rounded-full px-2 py-0.5 ml-2 flex-shrink-0">
                  {matter.doc_count} doc{matter.doc_count !== 1 ? "s" : ""}
                </span>
              </button>
            ))}
          </div>

          {/* Rename active matter */}
          {active && (
            <div className="border-t border-white/5">
              {renaming ? (
                <div className="p-3 flex gap-2">
                  <input
                    ref={renameInputRef}
                    value={renameName}
                    onChange={(e) => setRenameName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleRename();
                      if (e.key === "Escape") {
                        setRenaming(false);
                        setRenameName("");
                      }
                    }}
                    placeholder={active.display_name}
                    className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 outline-none focus:border-blue-500/50"
                  />
                  <button
                    onClick={handleRename}
                    className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm text-white transition-colors cursor-pointer"
                  >
                    Save
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setRenameName(active.display_name);
                    setRenaming(true);
                  }}
                  className="w-full text-left px-4 py-2.5 hover:bg-white/5 text-sm text-gray-400 cursor-pointer transition-colors flex items-center gap-2"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  Rename Case
                </button>
              )}
            </div>
          )}

          {/* Divider */}
          <div className="border-t border-white/5" />

          {/* New Case */}
          {creating ? (
            <div className="p-3 flex gap-2">
              <input
                ref={inputRef}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleNewCase();
                  if (e.key === "Escape") {
                    setCreating(false);
                    setNewName("");
                  }
                }}
                placeholder="Case name..."
                className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 outline-none focus:border-blue-500/50"
              />
              <button
                onClick={handleNewCase}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm text-white transition-colors"
              >
                Create
              </button>
            </div>
          ) : (
            <button
              onClick={() => setCreating(true)}
              className="w-full text-left px-4 py-2.5 hover:bg-white/5 text-sm text-blue-400 cursor-pointer transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Case
            </button>
          )}
        </div>
      )}
    </div>
  );
}
