/**
 * POST /api/auth/callback - Stores JWT tokens in httpOnly cookies (FR-053).
 *
 * Called by the /auth/callback page after receiving tokens from backend.
 * Stores tokens in secure, httpOnly cookies to prevent XSS attacks.
 */

import { NextResponse } from "next/server";
import { decodeJWTPayload } from "@/lib/auth";

export async function POST(request: Request) {
  let body: { access_token?: string; refresh_token?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  const { access_token, refresh_token } = body;

  if (!access_token || !refresh_token) {
    return NextResponse.json({ error: "Missing tokens" }, { status: 400 });
  }

  const response = NextResponse.json({ ok: true });

  // Access token cookie (30 min to match backend)
  response.cookies.set("docqa_access", access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 30 * 60, // 30 minutes
  });

  // Refresh token cookie (7 days to match backend)
  response.cookies.set("docqa_refresh", refresh_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 7 * 24 * 60 * 60, // 7 days
  });

  // Readable user claims cookie for frontend header construction.
  // Contains only public claims (no secrets) — safe as non-httpOnly.
  const claims = decodeJWTPayload(access_token);
  if (claims) {
    response.cookies.set(
      "docqa_user",
      JSON.stringify({
        userId: claims.sub,
        tenantId: claims.tenant_id,
        role: claims.role,
        name: claims.name || claims.email,
      }),
      {
        httpOnly: false,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 30 * 60, // Match access token TTL
      }
    );
  }

  return response;
}
