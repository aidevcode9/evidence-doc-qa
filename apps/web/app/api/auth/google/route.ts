/**
 * GET /api/auth/google - Initiates Google SSO redirect (FR-053).
 *
 * Redirects to backend SSO endpoint which handles the OAuth flow.
 */

import { NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const TENANT_ID = process.env.NEXT_PUBLIC_TENANT_ID || "demo-tenant";

export async function GET() {
  // Redirect to backend Google SSO endpoint
  const backendUrl = `${API_URL}/v1/auth/sso/google?tenant_id=${encodeURIComponent(TENANT_ID)}`;
  return NextResponse.redirect(backendUrl);
}
