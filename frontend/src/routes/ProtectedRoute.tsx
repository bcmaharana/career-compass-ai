import { useAuthStore } from "@/stores/auth-store";
import { Navigate, Outlet, useLocation } from "react-router-dom";

/**
 * Redirects to /login if there's no session in the auth store.
 *
 * Checks only for a token's *presence*, not its validity — an expired or
 * revoked token still reaches a protected route here, but the first API
 * call it makes will 401 and apiClient (api/client.ts) clears the stale
 * session automatically, which then bounces the user back to /login on
 * the next render. This keeps the guard itself simple and synchronous
 * rather than needing to await a token-verification call before
 * rendering anything.
 */
export function ProtectedRoute() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
