import { useAuthStore } from "@/stores/auth-store";
import { Navigate, Outlet, useLocation } from "react-router-dom";

/**
 * Redirects to "/" (the public landing page) if there's no session in the
 * auth store — not straight to /login, so an unauthenticated visitor
 * hitting a deep link sees the pitch/CTAs rather than a bare login form.
 *
 * Checks only for a token's *presence*, not its validity — an expired or
 * revoked token still reaches a protected route here, but the first API
 * call it makes will 401 and apiClient (api/client.ts) clears the stale
 * session automatically, which then bounces the user back to "/" on the
 * next render. This keeps the guard itself simple and synchronous rather
 * than needing to await a token-verification call before rendering
 * anything.
 */
export function ProtectedRoute() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
