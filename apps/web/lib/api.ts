/**
 * Centralized API client for Evidence Bound frontend.
 *
 * Manages authentication headers consistently across all API calls.
 * Currently uses AUTH_MODE=headers (demo headers). When AUTH_MODE=jwt
 * is enabled, this will be updated to use JWT Bearer tokens.
 *
 * TODO(FR-050): Replace hardcoded demo headers with JWT token extraction.
 * Current implementation grants admin role to all users - acceptable for
 * demo but MUST be changed before multi-tenant production deployment.
 * See: STATUS.md "Phase 5 Progress" for tracking.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let _currentMatterId =
  (typeof window !== "undefined" && localStorage.getItem("docqa_matter")) ||
  "";

/**
 * Set the active matter and persist to localStorage.
 */
export function setCurrentMatter(matterId: string): void {
  _currentMatterId = matterId;
  if (typeof window !== "undefined") {
    localStorage.setItem("docqa_matter", matterId);
  }
}

/**
 * Get the active matter ID.
 */
export function getCurrentMatter(): string {
  return _currentMatterId;
}

/**
 * Get authentication headers for API requests.
 *
 * For AUTH_MODE=headers (development/demo), returns X-* headers.
 * Future: For AUTH_MODE=jwt, will return Bearer token from cookie.
 *
 * WARNING: Hardcoded admin role bypasses matter access checks.
 * This is intentional for demo mode but grants full access.
 */
export function getAuthHeaders(): Record<string, string> {
  // TODO(FR-050): Replace with JWT token extraction when AUTH_MODE=jwt
  // Current hardcoded values are for demo/development only
  return {
    "X-Tenant-Id": "demo-tenant",
    "X-Matter-Id": _currentMatterId,
    "X-User-Id": "demo-user",
    "X-User-Role": "admin",
  };
}

/**
 * Get tenant-only headers (no X-Matter-Id) for matter-listing endpoints.
 */
function getTenantHeaders(): Record<string, string> {
  return {
    "X-Tenant-Id": "demo-tenant",
    "X-User-Id": "demo-user",
    "X-User-Role": "admin",
  };
}

/**
 * Make an authenticated JSON API request.
 *
 * @param endpoint - API endpoint (e.g., "/v1/docs")
 * @param options - Fetch options (method, body, etc.)
 * @returns Parsed JSON response
 * @throws Error with detail message on non-2xx response
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_URL}${endpoint}`;
  const headers: Record<string, string> = {
    ...getAuthHeaders(),
    ...(options.headers as Record<string, string>),
  };

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

/**
 * Upload a file with authentication.
 *
 * @param endpoint - API endpoint for upload
 * @param formData - FormData with file
 * @returns Raw Response object
 */
export async function apiUpload(
  endpoint: string,
  formData: FormData
): Promise<Response> {
  const url = `${API_URL}${endpoint}`;
  return fetch(url, {
    method: "POST",
    body: formData,
    headers: getAuthHeaders(),
  });
}

/**
 * Get the base API URL.
 */
export function getApiUrl(): string {
  return API_URL;
}

/**
 * Server capabilities from /healthz endpoint (FR-054, FR-055).
 */
export interface ServerCapabilities {
  status: string;
  parser_provider: "pypdf" | "marker" | "llamaparse";
  ocr_supported: boolean;
  supported_formats: string[];
  auth_bypass_enabled: boolean;
}

/**
 * Fetch server capabilities from /healthz endpoint.
 * Used by frontend to adapt UI (e.g., hide Google SSO when auth bypassed,
 * show "PDF only" when pypdf mode).
 */
export async function fetchCapabilities(): Promise<ServerCapabilities> {
  const response = await fetch(`${API_URL}/healthz`);
  if (!response.ok) {
    throw new Error("Failed to fetch server capabilities");
  }
  return response.json();
}

/**
 * Matter info returned by GET /v1/matters.
 */
export type MatterInfo = {
  matter_id: string;
  display_name: string;
  doc_count: number;
  latest_snapshot_id: string | null;
};

/**
 * Document summary returned by GET /v1/matters/{id}/docs.
 */
export type DocSummary = {
  doc_id: string;
  doc_name: string;
  status: string;
  ingested_at_utc: string;
  page_count: number | null;
};

/**
 * Fetch all matters the user can access (uses tenant-only headers).
 */
export async function fetchMatters(): Promise<MatterInfo[]> {
  const response = await fetch(`${API_URL}/v1/matters`, {
    headers: getTenantHeaders(),
  });
  if (!response.ok) {
    throw new Error("Failed to fetch matters");
  }
  return response.json();
}

/**
 * Fetch documents for a specific matter.
 */
export async function fetchMatterDocs(matterId: string): Promise<DocSummary[]> {
  const response = await fetch(`${API_URL}/v1/matters/${encodeURIComponent(matterId)}/docs`, {
    headers: getTenantHeaders(),
  });
  if (!response.ok) {
    throw new Error("Failed to fetch matter documents");
  }
  return response.json();
}

/**
 * Create a matter with a user-provided display name.
 * Idempotent — if the matter already exists, this is a no-op.
 */
export async function createMatter(matterId: string, displayName: string): Promise<void> {
  const response = await fetch(`${API_URL}/v1/matters`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getTenantHeaders(),
    },
    body: JSON.stringify({ matter_id: matterId, display_name: displayName }),
  });
  if (!response.ok && response.status !== 409) {
    throw new Error("Failed to create matter");
  }
}

/**
 * Rename a matter's display name.
 */
export async function renameMatter(matterId: string, displayName: string): Promise<void> {
  const response = await fetch(
    `${API_URL}/v1/matters/${encodeURIComponent(matterId)}/name`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...getTenantHeaders(),
      },
      body: JSON.stringify({ display_name: displayName }),
    }
  );
  if (!response.ok) {
    throw new Error("Failed to rename matter");
  }
}
