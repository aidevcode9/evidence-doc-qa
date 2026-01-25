"use client";

/**
 * /auth/callback - OAuth callback handler page (FR-053).
 *
 * Receives tokens from backend SSO redirect, stores them via API route,
 * then redirects to the main application.
 */

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      const accessToken = searchParams.get("access_token");
      const refreshToken = searchParams.get("refresh_token");
      const errorMsg = searchParams.get("error");

      if (errorMsg) {
        setError(decodeURIComponent(errorMsg));
        return;
      }

      if (!accessToken || !refreshToken) {
        setError("Missing authentication tokens. Please try again.");
        return;
      }

      try {
        // Store tokens via API route (sets httpOnly cookies)
        const res = await fetch("/api/auth/callback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            access_token: accessToken,
            refresh_token: refreshToken,
          }),
        });

        if (!res.ok) {
          setError("Failed to complete authentication. Please try again.");
          return;
        }

        // Clear tokens from URL for security
        window.history.replaceState({}, "", "/auth/callback");

        // Redirect to main app
        router.replace("/");
      } catch {
        setError("Authentication request failed. Please try again.");
      }
    };

    handleCallback();
  }, [searchParams, router]);

  if (error) {
    return (
      <div className="text-center max-w-md p-6">
        <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-6 h-6 text-red-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold mb-2">Authentication Failed</h2>
        <p className="text-gray-400 mb-6">{error}</p>
        <a
          href="/login"
          className="inline-block px-6 py-3 bg-white text-black font-semibold rounded-xl hover:bg-white/90 transition"
        >
          Return to Login
        </a>
      </div>
    );
  }

  return (
    <div className="text-center">
      <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
      <p className="text-gray-400">Completing sign-in...</p>
    </div>
  );
}

function LoadingFallback() {
  return (
    <div className="text-center">
      <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
      <p className="text-gray-400">Loading...</p>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <div className="min-h-screen flex flex-col bg-black text-white">
      <header className="flex-none h-16 border-b border-white/10 flex items-center px-6 bg-black/50 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
            <span className="font-display font-bold text-black text-xl">E</span>
          </div>
          <h1 className="text-lg font-display font-bold tracking-tight">
            Evidence Bound
          </h1>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center">
        <Suspense fallback={<LoadingFallback />}>
          <CallbackHandler />
        </Suspense>
      </main>
    </div>
  );
}
