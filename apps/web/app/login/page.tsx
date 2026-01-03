"use client";

import React, { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

type LoginPayload = {
  name: string;
  email: string;
  betaCode: string;
};

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [betaCode, setBetaCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
  }, []);

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

      const nextPath = searchParams.get("next") || "/";
      router.replace(nextPath);
    } catch (err) {
      setError("Unable to authenticate. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

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

            <p className="mt-4 text-xs text-gray-500">
              By continuing you consent to demo telemetry.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
