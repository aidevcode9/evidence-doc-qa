/**
 * Auth utilities for JWT handling (FR-053).
 *
 * Client-side JWT decoding for display purposes only.
 * Actual validation happens server-side.
 */

export interface JWTClaims {
  sub: string; // user_id
  tenant_id: string;
  role: string;
  email: string;
  name?: string; // display name (OIDC standard claim)
  exp: number; // Unix timestamp
  iat: number;
  jti: string;
  type: "access" | "refresh";
}

export interface User {
  userId: string;
  email: string;
  role: string;
  tenantId: string;
  displayName: string;
}

/**
 * Decode JWT payload without validation (client-side display only).
 * Validation happens server-side via httpOnly cookie.
 */
export function decodeJWTPayload(token: string): JWTClaims | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload as JWTClaims;
  } catch {
    return null;
  }
}

/**
 * Check if token is expired (with buffer for refresh).
 */
export function isTokenExpired(claims: JWTClaims, bufferSeconds = 60): boolean {
  const now = Math.floor(Date.now() / 1000);
  return claims.exp - bufferSeconds < now;
}

/**
 * Extract user info from JWT claims.
 */
export function claimsToUser(claims: JWTClaims): User {
  return {
    userId: claims.sub,
    email: claims.email,
    role: claims.role,
    tenantId: claims.tenant_id,
    displayName: claims.name || claims.email,
  };
}

/**
 * Get auth mode from environment.
 */
export function getAuthMode(): "jwt" | "headers" {
  if (typeof window !== "undefined") {
    // Client-side: check public env var
    return process.env.NEXT_PUBLIC_AUTH_MODE === "jwt" ? "jwt" : "headers";
  }
  // Server-side
  return process.env.NEXT_PUBLIC_AUTH_MODE === "jwt" ? "jwt" : "headers";
}
