/**
 * POST /api/auth/logout - Clears auth cookies and revokes refresh token (FR-053).
 *
 * Calls backend to revoke the refresh token, then clears all auth cookies.
 */

import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get("docqa_refresh")?.value;

  // Revoke token on backend (best effort - don't fail if this fails)
  if (refreshToken) {
    try {
      await fetch(`${API_URL}/v1/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // Ignore errors - we'll clear cookies anyway
    }
  }

  const response = NextResponse.json({ ok: true });

  // Clear all auth cookies
  response.cookies.delete("docqa_access");
  response.cookies.delete("docqa_refresh");
  response.cookies.delete("docqa_beta"); // Clear legacy beta cookie too

  return response;
}
