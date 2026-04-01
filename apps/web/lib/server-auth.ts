import { NextRequest } from "next/server";

export type CookieUser = {
  userId: string;
  tenantId: string;
  role: string;
  name?: string;
  email?: string;
};

const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE === "jwt" ? "jwt" : "headers";

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

export function buildBackendAuthHeaders(
  request: NextRequest,
  options: { matterId?: string } = {}
): Headers {
  const headers = new Headers();
  const matterId = options.matterId ?? request.headers.get("x-matter-id");
  const betaSession = request.cookies.get("docqa_beta")?.value;
  const user = parseCookieUser(request.cookies.get("docqa_user")?.value);

  if (matterId) {
    headers.set("X-Matter-Id", matterId);
  }

  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }

  const accept = request.headers.get("accept");
  if (accept) {
    headers.set("Accept", accept);
  }

  for (const headerName of ["x-docqa-session", "x-docqa-user-email", "x-docqa-user-name"]) {
    const value = request.headers.get(headerName);
    if (value) {
      headers.set(headerName, value);
    }
  }

  if (AUTH_MODE === "jwt") {
    const accessToken = request.cookies.get("docqa_access")?.value;
    if (accessToken) {
      headers.set("Authorization", `Bearer ${accessToken}`);
      return headers;
    }

    // Backward-compatible beta gate support: older demo/prod environments still
    // rely on the httpOnly beta session plus readable user claims cookie.
    if (betaSession && user?.userId && user.tenantId && user.role) {
      headers.set("X-Tenant-Id", user.tenantId);
      headers.set("X-User-Id", user.userId);
      headers.set("X-User-Role", user.role);
      return headers;
    }

    throw new Error("Authentication required");
  }

  if (!user?.userId || !user.tenantId || !user.role) {
    throw new Error("Authentication required");
  }

  headers.set("X-Tenant-Id", user.tenantId);
  headers.set("X-User-Id", user.userId);
  headers.set("X-User-Role", user.role);
  return headers;
}
