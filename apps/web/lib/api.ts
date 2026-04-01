/**
 * Centralized API client for Evidence Bound frontend.
 *
 * Authenticated requests go through the Next.js proxy so JWT cookies stay
 * server-side in browser sessions.
 */

const BACKEND_API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PROXY_API_URL = "/api/backend";
const SESSION_KEY_PREFIX = "docqa_session:";

export type CachedUser = {
  userId: string;
  tenantId: string;
  role: string;
  name?: string;
  email?: string;
};

let _currentMatterId =
  (typeof window !== "undefined" && localStorage.getItem("docqa_matter")) || "";

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
 * Read user claims from the docqa_user cookie when available.
 */
export function getCachedUser(): CachedUser | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("docqa_user="));
  if (!match) return null;
  try {
    return JSON.parse(decodeURIComponent(match.split("=")[1])) as CachedUser;
  } catch {
    return null;
  }
}

/**
 * Headers needed by the web proxy for matter-scoped routes.
 */
export function getAuthHeaders(): Record<string, string> {
  if (!_currentMatterId) return {};
  return {
    "X-Matter-Id": _currentMatterId,
  };
}

/**
 * Make an authenticated JSON API request through the Next.js proxy.
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${PROXY_API_URL}${endpoint}`, {
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...(options.headers as Record<string, string> | undefined),
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * Upload a file with matter context through the Next.js proxy.
 */
export async function apiUpload(
  endpoint: string,
  formData: FormData
): Promise<Response> {
  return fetch(`${PROXY_API_URL}${endpoint}`, {
    method: "POST",
    body: formData,
    headers: getAuthHeaders(),
  });
}

/**
 * Get the authenticated API base URL exposed to client components.
 */
export function getApiUrl(): string {
  return PROXY_API_URL;
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

export async function fetchCapabilities(): Promise<ServerCapabilities> {
  const response = await fetch(`${BACKEND_API_URL}/healthz`);
  if (!response.ok) {
    throw new Error("Failed to fetch server capabilities");
  }
  return response.json();
}

export type MatterInfo = {
  matter_id: string;
  display_name: string;
  doc_count: number;
  latest_snapshot_id: string | null;
  last_question_at: string | null;
  last_question_preview: string | null;
  created_at_utc?: string | null;
};

export type DocSummary = {
  doc_id: string;
  doc_name: string;
  status: string;
  ingested_at_utc: string;
  page_count: number | null;
};

export async function fetchMatters(): Promise<MatterInfo[]> {
  return apiRequest<MatterInfo[]>("/v1/matters");
}

export async function fetchMatter(matterId: string): Promise<MatterInfo> {
  return apiRequest<MatterInfo>(`/v1/matters/${encodeURIComponent(matterId)}`);
}

export async function fetchMatterDocs(matterId: string): Promise<DocSummary[]> {
  return apiRequest<DocSummary[]>(
    `/v1/matters/${encodeURIComponent(matterId)}/docs`
  );
}

export async function createMatter(
  matterId: string,
  displayName: string
): Promise<MatterInfo | { matter_id: string; display_name: string }> {
  return apiRequest(`/v1/matters`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ matter_id: matterId, display_name: displayName }),
  });
}

export async function deleteMatter(matterId: string): Promise<void> {
  await apiRequest(`/v1/admin/matters/${encodeURIComponent(matterId)}`, {
    method: "DELETE",
  });
}

export async function renameMatter(
  matterId: string,
  displayName: string
): Promise<void> {
  await apiRequest(`/v1/matters/${encodeURIComponent(matterId)}/name`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ display_name: displayName }),
  });
}

export function getMatterSessionStorageKey(matterId: string): string {
  const tenantId = getCachedUser()?.tenantId || "anonymous";
  return `${SESSION_KEY_PREFIX}${tenantId}:${matterId}`;
}

export function getMatterSessionId(matterId: string): string | null {
  if (typeof window === "undefined") return null;

  const scopedKey = getMatterSessionStorageKey(matterId);
  const scopedSession = localStorage.getItem(scopedKey);
  if (scopedSession) {
    return scopedSession;
  }

  const legacySession = localStorage.getItem("docqa_session");
  if (legacySession) {
    localStorage.setItem(scopedKey, legacySession);
    localStorage.removeItem("docqa_session");
    return legacySession;
  }

  return null;
}

export function setMatterSessionId(matterId: string, sessionId: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(getMatterSessionStorageKey(matterId), sessionId);
}

export function clearStoredSessions(): void {
  if (typeof window === "undefined") return;

  const keysToRemove: string[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key && key.startsWith(SESSION_KEY_PREFIX)) {
      keysToRemove.push(key);
    }
  }

  for (const key of keysToRemove) {
    localStorage.removeItem(key);
  }
  localStorage.removeItem("docqa_session");
}
