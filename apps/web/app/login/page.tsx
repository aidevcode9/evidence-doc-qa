"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getAuthMode } from "@/lib/auth";
import { fetchCapabilities, type ServerCapabilities } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Logo } from "@/components/Logo";

type LoginPayload = {
  name: string;
  email: string;
  betaCode: string;
};

function getSafeRedirectUrl(url: string | null): string {
  if (!url) return "/";
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
      const timer = setTimeout(() => setLoggedOut(false), 5000);
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
        // Ignore
      }
    }

    fetchCapabilities()
      .then((caps) => {
        setCapabilities(caps);
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
      await response.json();
      localStorage.setItem(
        "docqa_user",
        JSON.stringify({ name: trimmedName, email: trimmedEmail })
      );

      router.replace(nextPath);
    } catch {
      setError("Unable to authenticate. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const showGoogleSSO = getAuthMode() === "jwt" && !capabilities?.auth_bypass_enabled;

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-background text-foreground">
      {/* ── Left panel: Brand experience ── */}
      <div className="hidden lg:flex lg:w-[55%] relative overflow-hidden items-center justify-center">
        {/* Aurora gradient mesh background */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-background to-accent/10" />
        <div className="absolute top-0 left-0 w-full h-full">
          <div className="absolute top-[-10%] left-[-10%] w-[60%] h-[60%] rounded-full bg-primary/15 blur-[100px] animate-pulse [animation-duration:8s]" />
          <div className="absolute bottom-[-5%] right-[-5%] w-[50%] h-[50%] rounded-full bg-accent/20 blur-[80px] animate-pulse [animation-duration:6s] [animation-delay:2s]" />
          <div className="absolute top-[40%] left-[50%] w-[30%] h-[30%] rounded-full bg-primary/10 blur-[60px] animate-pulse [animation-duration:10s] [animation-delay:4s]" />
        </div>

        {/* Subtle grid overlay */}
        <div className="absolute inset-0 bg-grid-pattern opacity-50 pointer-events-none" />

        {/* Geometric accent shapes */}
        <div className="absolute top-20 right-20 w-24 h-24 border border-primary/10 rounded-2xl rotate-12" />
        <div className="absolute bottom-32 left-16 w-16 h-16 border border-accent/15 rounded-xl -rotate-6" />
        <div className="absolute top-1/3 right-1/4 w-3 h-3 rounded-full bg-accent/30" />
        <div className="absolute bottom-1/4 left-1/3 w-2 h-2 rounded-full bg-primary/30" />

        <div className="relative max-w-lg z-10 px-12">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-16">
            <Logo size={40} />
            <span className="text-sm font-medium tracking-wide text-muted-foreground">Evidence Bound</span>
          </div>

          {/* Headline — the hero moment */}
          <div className="space-y-2">
            <h1 className="font-serif text-[3.5rem] lg:text-[4rem] leading-[1.05] tracking-tight text-foreground">
              Every answer,
            </h1>
            <h1 className="font-serif text-[3.5rem] lg:text-[4rem] leading-[1.05] tracking-tight">
              <span className="italic bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
                backed by evidence.
              </span>
            </h1>
          </div>

          <p className="text-base text-muted-foreground leading-relaxed max-w-sm mt-8">
            AI-powered document analysis for legal teams. Ask questions, get verified citations from your case files.
          </p>

          {/* Trust signals */}
          <div className="mt-14 flex items-center gap-8">
            <div className="flex flex-col">
              <span className="text-2xl font-semibold text-foreground">95%+</span>
              <span className="text-[11px] text-muted-foreground mt-0.5 uppercase tracking-wider">Citation accuracy</span>
            </div>
            <div className="w-px h-10 bg-border" />
            <div className="flex flex-col">
              <span className="text-2xl font-semibold text-foreground">&lt;8s</span>
              <span className="text-[11px] text-muted-foreground mt-0.5 uppercase tracking-wider">Query response</span>
            </div>
            <div className="w-px h-10 bg-border" />
            <div className="flex flex-col">
              <span className="text-2xl font-semibold text-foreground">Zero</span>
              <span className="text-[11px] text-muted-foreground mt-0.5 uppercase tracking-wider">Hallucinations</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Right panel: Login form ── */}
      <div className="flex-1 flex flex-col min-h-screen lg:min-h-0">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5 lg:hidden">
            <Logo size={28} />
            <span className="font-semibold text-sm text-foreground">Evidence Bound</span>
          </div>
          <div className="hidden lg:block" />
          <ThemeToggle />
        </div>

        <div className="flex-1 flex items-center justify-center px-6 pb-12">
          <div className="w-full max-w-sm">
            {/* Mobile headline */}
            <div className="lg:hidden mb-10 text-center">
              <h1 className="font-serif text-3xl tracking-tight text-foreground leading-tight">
                Every answer,{" "}
                <span className="italic bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
                  backed by evidence.
                </span>
              </h1>
              <p className="text-sm text-muted-foreground mt-3">
                AI-powered document Q&A for legal teams.
              </p>
            </div>

            {loggedOut && (
              <div className="mb-4 text-sm text-success border border-success/30 bg-success/10 rounded-lg px-4 py-3 flex items-center gap-2">
                <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Signed out successfully.
              </div>
            )}

            <div className="mb-8">
              <p className="text-xs uppercase tracking-[0.2em] text-primary font-semibold mb-2">
                Beta Access
              </p>
              <h2 className="text-xl font-semibold text-foreground">
                Sign in to continue
              </h2>
              <p className="text-sm text-muted-foreground mt-1.5">
                Enter your details and beta code to access the demo.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ada Lovelace"
                  className="w-full bg-background border border-input rounded-lg px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/40 focus:ring-2 focus:ring-ring/20 focus:border-ring outline-none transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full bg-background border border-input rounded-lg px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/40 focus:ring-2 focus:ring-ring/20 focus:border-ring outline-none transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                  Beta Code
                </label>
                <input
                  type="password"
                  value={betaCode}
                  onChange={(e) => setBetaCode(e.target.value)}
                  placeholder="Invite code"
                  className="w-full bg-background border border-input rounded-lg px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/40 focus:ring-2 focus:ring-ring/20 focus:border-ring outline-none transition-all"
                />
              </div>

              {error && (
                <div className="text-sm text-destructive border border-destructive/30 bg-destructive/10 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}

              <Button
                type="submit"
                disabled={isSubmitting}
                className="w-full h-10 rounded-lg text-sm font-medium"
              >
                {isSubmitting ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Authenticating...
                  </span>
                ) : (
                  "Enter Demo"
                )}
              </Button>
            </form>

            {showGoogleSSO && (
              <>
                <div className="relative my-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-border" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="bg-background px-3 text-muted-foreground">or</span>
                  </div>
                </div>

                <a
                  href="/api/auth/google"
                  className="w-full flex items-center justify-center gap-2.5 rounded-lg border border-border bg-card py-2.5 text-sm font-medium transition-colors hover:bg-muted"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                  Sign in with Google
                </a>
              </>
            )}

            <p className="mt-6 text-xs text-muted-foreground text-center">
              By continuing you consent to demo telemetry.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
