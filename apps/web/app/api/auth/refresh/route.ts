/**
 * POST /api/auth/refresh - Refreshes access token using refresh token (FR-053).
 *
 * Reads refresh token from httpOnly cookie, calls backend to get new access token,
 * and updates the access token cookie.
 */

import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get("docqa_refresh")?.value;

  if (!refreshToken) {
    return NextResponse.json({ error: "No refresh token" }, { status: 401 });
  }

  try {
    // Call backend refresh endpoint
    const res = await fetch(`${API_URL}/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      // Clear cookies on refresh failure
      const response = NextResponse.json({ error: "Refresh failed" }, { status: 401 });
      response.cookies.delete("docqa_access");
      response.cookies.delete("docqa_refresh");
      return response;
    }

    const data = await res.json();
    const response = NextResponse.json({ ok: true });

    // Update access token cookie
    response.cookies.set("docqa_access", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 30 * 60, // 30 minutes
    });

    return response;
  } catch {
    return NextResponse.json({ error: "Refresh request failed" }, { status: 502 });
  }
}
