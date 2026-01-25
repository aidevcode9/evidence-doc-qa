/**
 * GET /api/auth/me - Returns current user from JWT cookie (FR-053).
 *
 * Decodes the access token from httpOnly cookie and returns user info.
 * Token validation is minimal here; backend validates on API calls.
 */

import { NextRequest, NextResponse } from "next/server";
import { decodeJWTPayload, claimsToUser, isTokenExpired } from "@/lib/auth";

export async function GET(request: NextRequest) {
  const accessToken = request.cookies.get("docqa_access")?.value;

  if (!accessToken) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const claims = decodeJWTPayload(accessToken);
  if (!claims) {
    return NextResponse.json({ error: "Invalid token" }, { status: 401 });
  }

  // Check expiry (without buffer since this is just for display)
  if (isTokenExpired(claims, 0)) {
    return NextResponse.json({ error: "Token expired" }, { status: 401 });
  }

  return NextResponse.json({ user: claimsToUser(claims) });
}
