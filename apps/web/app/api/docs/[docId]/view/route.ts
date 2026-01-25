/**
 * Proxy route for document viewing in iframes.
 *
 * Iframes cannot send custom HTTP headers, so this route proxies
 * requests to the backend API with authentication headers.
 *
 * Security measures:
 * - SSRF protection: validates API_URL against allowlist
 * - Path traversal prevention: validates docId format
 * - Timeout: prevents hanging connections
 * - CSP: prevents script execution in PDF content
 */

import { NextRequest, NextResponse } from "next/server";
import { getAuthHeaders } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Request timeout in milliseconds (30 seconds)
const FETCH_TIMEOUT_MS = 30000;

// Validate docId format to prevent path traversal
const DOC_ID_PATTERN = /^[a-zA-Z0-9][-a-zA-Z0-9]{0,63}$/;

// Allowlisted API hosts for SSRF protection
// Configure ALLOWED_API_HOST env var for production deployments
const ALLOWED_API_HOSTS = [
  "localhost",
  "127.0.0.1",
  ...(process.env.ALLOWED_API_HOST ? [process.env.ALLOWED_API_HOST] : []),
];

/**
 * Validate that API_URL points to an allowed host (SSRF protection).
 */
function isAllowedApiHost(urlString: string): boolean {
  try {
    const url = new URL(urlString);
    return ALLOWED_API_HOSTS.some(
      (host) => url.hostname === host || url.hostname.endsWith(`.${host}`)
    );
  } catch {
    return false;
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ docId: string }> }
) {
  const { docId } = await params;

  // Validate docId format (security: prevent path traversal)
  if (!DOC_ID_PATTERN.test(docId)) {
    return NextResponse.json(
      { error: "Invalid document ID format" },
      { status: 400 }
    );
  }

  // SSRF protection: validate API_URL points to allowed host
  if (!isAllowedApiHost(API_URL)) {
    // Log internally but don't expose details to client
    console.error("SSRF protection: blocked request to non-allowlisted host");
    return NextResponse.json(
      { error: "Service configuration error" },
      { status: 500 }
    );
  }

  // Create abort controller for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_URL}/v1/docs/${docId}/view`, {
      headers: getAuthHeaders(),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return NextResponse.json(
        { error: "Document not found" },
        { status: response.status }
      );
    }

    const blob = await response.blob();
    const contentType = response.headers.get("Content-Type") || "application/pdf";

    return new NextResponse(blob, {
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": response.headers.get("Content-Disposition") || "",
        // Security headers
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        // CSP: prevent script execution in PDF/image content
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
      },
    });
  } catch (error) {
    clearTimeout(timeoutId);

    // Handle timeout specifically
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json(
        { error: "Request timeout" },
        { status: 504 }
      );
    }

    // Log error without exposing backend details
    console.error("Document proxy error:", error instanceof Error ? error.message : "Unknown error");
    return NextResponse.json(
      { error: "Failed to fetch document" },
      { status: 502 }
    );
  }
}
