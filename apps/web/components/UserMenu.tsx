"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { User } from "@/lib/auth";

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  attorney: "bg-green-500/20 text-green-400 border-green-500/30",
  paralegal: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  viewer: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

function getInitials(user: User | null): string {
  if (!user) return "D";
  const email = user.email || "";
  return email.charAt(0).toUpperCase() || "?";
}

export function UserMenu() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isDemo, setIsDemo] = useState(false);
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/auth/me")
      .then((res) => {
        if (!res.ok) {
          setIsDemo(true);
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (data?.user) setUser(data.user);
      })
      .catch(() => setIsDemo(true));
  }, []);

  const handleClose = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;

    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        handleClose();
      }
    }
    function onEscape(e: KeyboardEvent) {
      if (e.key === "Escape") handleClose();
    }

    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onEscape);
    };
  }, [open, handleClose]);

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // Clear cookies failed — redirect anyway
    }
    localStorage.removeItem("docqa_user");
    localStorage.removeItem("docqa_session");
    router.push("/login?logged_out=1");
  };

  const initials = getInitials(user);
  const displayName = isDemo ? "Demo User" : user?.email?.split("@")[0] || "User";
  const displayEmail = isDemo ? "Auth bypass enabled" : user?.email || "";
  const role = isDemo ? "demo" : user?.role || "viewer";
  const roleStyle = ROLE_COLORS[role] || ROLE_COLORS.viewer;

  return (
    <div ref={menuRef} className="relative">
      {/* Avatar Button */}
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="w-8 h-8 rounded-full bg-white/10 border border-white/10 flex items-center justify-center text-sm font-semibold text-gray-300 hover:bg-white/20 hover:border-white/20 transition-colors cursor-pointer"
        aria-label="User menu"
        aria-expanded={open}
      >
        {isDemo ? (
          <svg className="w-4 h-4 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        ) : (
          initials
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-64 bg-zinc-900/95 backdrop-blur-md border border-white/10 rounded-xl shadow-2xl overflow-hidden z-20 animate-in fade-in slide-in-from-top-1 duration-150">
          {/* User Info */}
          <div className="px-4 py-3 border-b border-white/10">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-white/10 flex items-center justify-center text-sm font-semibold text-gray-300 flex-shrink-0">
                {isDemo ? (
                  <svg className="w-4 h-4 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                ) : (
                  initials
                )}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-200 truncate">{displayName}</div>
                <div className="text-xs text-gray-500 truncate">{displayEmail}</div>
              </div>
            </div>
            <div className="mt-2">
              <span className={`inline-flex items-center text-[10px] uppercase tracking-wider font-medium px-2 py-0.5 rounded-full border ${roleStyle}`}>
                {role}
              </span>
            </div>
          </div>

          {/* Sign Out */}
          <div className="p-1.5">
            <button
              onClick={handleSignOut}
              disabled={signingOut}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-400 hover:text-red-400 hover:bg-white/5 rounded-lg transition-colors disabled:opacity-50 cursor-pointer"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              {signingOut ? "Signing out..." : "Sign out"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
