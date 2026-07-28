/**
 * Thin fetch wrapper around the backend API.
 *
 * Types come from `src/api/schema.gen.ts`, generated from the backend's
 * OpenAPI schema via `npm run generate:api-types` (requires the backend
 * running locally at http://localhost:8000). Regenerate whenever the
 * backend's API contract changes — never hand-edit schema.gen.ts.
 *
 * This file is intentionally the *only* place that knows about fetch,
 * base URLs, auth-header injection, and the backend's error response
 * shape. Feature modules call the typed query/mutation hooks in
 * api/queries/*, never this file directly.
 */

import { useAuthStore } from "@/stores/auth-store";
import { queryClient } from "@/lib/query-client";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
  };
}

export class ApiError extends Error {
  readonly code: string;
  readonly requestId: string | null;
  readonly status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.error.code;
    this.requestId = body.error.request_id;
  }
}

// Empty string -> same-origin requests, proxied to the backend by Vite in
// dev (see vite.config.ts) and by the gateway/load balancer in production.
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Read directly from the store rather than a React hook — this
  // function isn't a component/hook itself, so it uses Zustand's
  // vanilla getState() rather than the useAuthStore() hook form.
  const accessToken = useAuthStore.getState().accessToken;

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    // Every earlier fix here operated at the React Query layer, which
    // sits entirely on top of whatever the browser's own HTTP cache
    // decides to do. If the browser ever served a cached response for
    // this exact URL — plausible for a GET hit repeatedly in quick
    // succession, and nothing in this file previously told it not to —
    // React Query would have faithfully cached and displayed that
    // stale body, genuinely believing it was fresh, since fetch()
    // itself never told it otherwise. `cache: "no-store"` forces every
    // request to actually hit the network/server, never a cached copy.
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init?.headers,
    },
  });

  // Sliding session: the backend reissues a fresh token once the
  // current one is past the halfway point of its lifetime (see
  // app/api/dependencies.py's get_current_identity). Swapped in
  // silently — no user-visible effect beyond the session simply not
  // expiring while they're actively using the app.
  const refreshedToken = response.headers.get("X-Refreshed-Token");
  if (refreshedToken) {
    useAuthStore.getState().updateAccessToken(refreshedToken);
  }

  if (!response.ok) {
    let body: ApiErrorBody;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = { error: { code: "UNKNOWN_ERROR", message: response.statusText, request_id: null } };
    }

    // A 401 on an authenticated request means the token is invalid or
    // expired — clear the stale session so the UI reflects "logged out"
    // rather than silently retrying with a token that will never work.
    if (response.status === 401 && accessToken) {
      useAuthStore.getState().clearSession();
      queryClient.clear();
    }

    throw new ApiError(response.status, body);
  }

  // 204 No Content and similar have no body to parse.
  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  /**
   * Multipart file upload. Deliberately bypasses the JSON Content-Type
   * header `request()` normally sets — the browser needs to set its own
   * `multipart/form-data; boundary=...` header for a FormData body, so
   * this passes an empty headers override rather than reusing request().
   */
  uploadFile: async <T>(path: string, file: File, fieldName = "file"): Promise<T> => {
    const accessToken = useAuthStore.getState().accessToken;
    const formData = new FormData();
    formData.append(fieldName, file);

    const response = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      cache: "no-store",
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      body: formData,
    });

    const refreshedToken = response.headers.get("X-Refreshed-Token");
    if (refreshedToken) {
      useAuthStore.getState().updateAccessToken(refreshedToken);
    }

    if (!response.ok) {
      let body: ApiErrorBody;
      try {
        body = (await response.json()) as ApiErrorBody;
      } catch {
        body = { error: { code: "UNKNOWN_ERROR", message: response.statusText, request_id: null } };
      }
      throw new ApiError(response.status, body);
    }

    return (await response.json()) as T;
  },
};
