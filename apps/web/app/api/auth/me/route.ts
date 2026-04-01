/**
 * GET /api/auth/me - Returns current user from JWT cookie (FR-053).
 *
 * Decodes the access token from httpOnly cookie and returns user info.
 * Token validation is minimal here; backend validates on API calls.
 */

import { NextRequest, NextResponse } from "next/server";
import { decodeJWTPayload, claimsToUser, isTokenExpired } from "@/lib/auth";
import type { CookieUser } from "@/lib/server-auth";

function parseCookieUser(rawValue?: string): CookieUser | null {
  if (!rawValue) return null;
  try {
    return JSON.parse(rawValue) as CookieUser;
  } catch {
    try {
      return JSON.parse(decodeURIComponent(rawValue)) as CookieUser;
    } catch {
      return null;
    }
  }
}

export async function GET(request: NextRequest) {
  const accessToken = request.cookies.get("docqa_access")?.value;
  const betaSession = request.cookies.get("docqa_beta")?.value;

  if (!accessToken) {
    const betaUser = parseCookieUser(request.cookies.get("docqa_user")?.value);
    if (betaSession && betaUser?.userId && betaUser.tenantId && betaUser.role) {
      return NextResponse.json({
        user: {
          userId: betaUser.userId,
          email: betaUser.email || "",
          role: betaUser.role,
          tenantId: betaUser.tenantId,
          displayName: betaUser.name || betaUser.email || betaUser.userId,
        },
      });
    }
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
