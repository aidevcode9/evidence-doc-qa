"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getAuthMode } from "@/lib/auth";
import { fetchCapabilities, type ServerCapabilities } from "@/lib/api";

type LoginPayload = {
  name: string;
  email: string;
  betaCode: string;
};

/**
 * Sanitize redirect URL to prevent open redirect attacks.
 * Only allows relative paths starting with "/" (not "//").
 */
function getSafeRedirectUrl(url: string | null): string {
  if (!url) return "/";
  // Must start with "/" but not "//" (protocol-relative URL)
  if (url.startsWith("/") && !url.startsWith("//")) {
    return url;
  }
  return "/";
}

export default function LoginPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [betaCode, setBetaCode] = useState("");
  const [nextPath, setNextPath] = useState("/");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<ServerCapabilities | null>(null);
  const [loggedOut, setLoggedOut] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const safeNextPath = getSafeRedirectUrl(params.get("next"));
    setNextPath(safeNextPath);

    if (params.get("logged_out") === "1") {
      setLoggedOut(true);
      // Auto-dismiss after 5 seconds
      const timer = setTimeout(() => setLoggedOut(false), 5000);
      // Clean URL without triggering navigation
      window.history.replaceState({}, "", "/login");
      return () => clearTimeout(timer);
    }

    const storedUser = localStorage.getItem("docqa_user");
    if (storedUser) {
      try {
        const parsed = JSON.parse(storedUser) as { name?: string; email?: string };
        if (parsed.name) setName(parsed.name);
        if (parsed.email) setEmail(parsed.email);
      } catch {
        // Ignore invalid storage.
      }
    }

    // Fetch server capabilities to check if auth is bypassed
    fetchCapabilities()
      .then((caps) => {
        setCapabilities(caps);
        // Auto-redirect if auth bypass is enabled (FR-054)
        if (caps.auth_bypass_enabled) {
          router.replace(safeNextPath);
        }
      })
      .catch((err) => console.error("Failed to fetch capabilities:", err));
  }, [router]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    const trimmedName = name.trim();
    const trimmedEmail = email.trim();
    const trimmedCode = betaCode.trim();

    if (!trimmedName || !trimmedEmail || !trimmedCode) {
      setError("All fields are required.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: LoginPayload = {
        name: trimmedName,
        email: trimmedEmail,
        betaCode: trimmedCode,
      };

      const response = await fetch("/api/auth/beta", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(data.error || "Invalid beta code.");
        return;
      }

      const data = await response.json();
      if (data.sessionId) {
        localStorage.setItem("docqa_session", data.sessionId);
      }
      localStorage.setItem(
        "docqa_user",
        JSON.stringify({ name: trimmedName, email: trimmedEmail })
      );

      router.replace(nextPath);
    } catch (err) {
      setError("Unable to authenticate. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Show Google SSO only if: JWT mode AND auth bypass is NOT enabled
  const showGoogleSSO = getAuthMode() === "jwt" && !capabilities?.auth_bypass_enabled;

  return (
    <div className="min-h-screen flex flex-col bg-black text-white">
      <header className="flex-none h-16 border-b border-white/10 flex items-center justify-between px-6 bg-black/50 backdrop-blur-md z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
            <span className="font-display font-bold text-black text-xl">E</span>
          </div>
          <div>
            <h1 className="text-lg font-display font-bold tracking-tight leading-none">
              Evidence Bound <span className="opacity-40 font-normal text-sm ml-1">v3.1</span>
            </h1>
          </div>
        </div>
      </header>

      <main className="flex-1 relative flex items-center justify-center overflow-hidden">
        <div className="absolute inset-0 bg-grid-pattern opacity-20 pointer-events-none" />
        <div className="relative w-full max-w-md mx-auto p-6">
          {loggedOut && (
            <div className="mb-4 text-sm text-green-400 border border-green-500/30 bg-green-500/10 rounded-xl px-4 py-3 flex items-center gap-2">
              <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Signed out successfully.
            </div>
          )}
          <div className="bg-zinc-900/70 border border-white/10 rounded-2xl p-6 shadow-2xl backdrop-blur">
            <div className="mb-6">
              <div className="text-xs uppercase tracking-[0.3em] text-blue-400/70 mb-2">
                Beta Access
              </div>
              <h2 className="text-2xl font-display font-semibold">
                Secure the evidence gate
              </h2>
              <p className="text-sm text-gray-400 mt-2">
                Enter your details and the beta code to access the Evidence Bound demo.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs uppercase tracking-widest text-gray-500 mb-2">
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ada Lovelace"
                  className="w-full bg-zinc-900/50 border border-white/10 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-600 focus:ring-1 focus:ring-blue-500 focus:border-blue-500/50 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs uppercase tracking-widest text-gray-500 mb-2">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full bg-zinc-900/50 border border-white/10 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-600 focus:ring-1 focus:ring-blue-500 focus:border-blue-500/50 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs uppercase tracking-widest text-gray-500 mb-2">
                  Beta Code
                </label>
                <input
                  type="password"
                  value={betaCode}
                  onChange={(e) => setBetaCode(e.target.value)}
                  placeholder="Invite code"
                  className="w-full bg-zinc-900/50 border border-white/10 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-600 focus:ring-1 focus:ring-blue-500 focus:border-blue-500/50 outline-none"
                />
              </div>

              {error && (
                <div className="text-sm text-red-400 border border-red-500/30 bg-red-500/10 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full rounded-xl bg-white text-black font-semibold py-3 text-sm transition hover:bg-white/90 disabled:opacity-60"
              >
                {isSubmitting ? "Authenticating..." : "Enter Demo"}
              </button>
            </form>

            {/* Google SSO Button - shown in JWT mode when auth bypass is NOT enabled (FR-054) */}
            {showGoogleSSO && (
              <>
                <div className="relative my-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-white/10" />
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="bg-zinc-900 px-4 text-gray-500">or</span>
                  </div>
                </div>

                <a
                  href="/api/auth/google"
                  className="w-full flex items-center justify-center gap-3 rounded-xl border border-white/20 bg-white/5 py-3 text-sm font-medium transition hover:bg-white/10"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <path
                      fill="#4285F4"
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    />
                    <path
                      fill="#34A853"
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    />
                    <path
                      fill="#FBBC05"
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    />
                    <path
                      fill="#EA4335"
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    />
                  </svg>
                  Sign in with Google
                </a>
              </>
            )}

            <p className="mt-4 text-xs text-gray-500">
              By continuing you consent to demo telemetry.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
