import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Middleware for route protection (FR-053).
 *
 * Checks for either JWT cookie (AUTH_MODE=jwt) or beta cookie (AUTH_MODE=headers).
 * Redirects to /login if not authenticated.
 */

const PUBLIC_PATHS = ["/login", "/auth/callback", "/api/auth"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip static assets
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.startsWith("/robots.txt") ||
    pathname.startsWith("/sitemap.xml")
  ) {
    return NextResponse.next();
  }

  // Allow public paths
  if (PUBLIC_PATHS.some((path) => pathname.startsWith(path))) {
    return NextResponse.next();
  }

  // Check for auth - JWT cookie OR beta cookie (backward compatible)
  const accessToken = request.cookies.get("docqa_access")?.value;
  const betaSession = request.cookies.get("docqa_beta")?.value;
  const isAuthenticated = !!accessToken || !!betaSession;

  if (!isAuthenticated) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: "/:path*",
};
