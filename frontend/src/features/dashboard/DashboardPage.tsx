import { useCurrentUser } from "@/api/queries/auth";
import { useHealthCheck } from "@/api/queries/health";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Placeholder dashboard. Its job so far is to prove the whole chain
 * works end to end: React Query hook -> typed API client -> real
 * FastAPI backend -> rendered result — first for the unauthenticated
 * health check, and now for an authenticated call (GET /identity/me)
 * too, now that Phase 1's identity service is wired up. Real dashboard
 * widgets (career readiness score, skill gaps, recommendations,
 * activity timeline) land with their owning feature modules in later
 * phases.
 */
export function DashboardPage() {
  const health = useHealthCheck();
  const currentUser = useCurrentUser();

  return (
    <div className="grid max-w-2xl gap-4 sm:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Backend connectivity</CardTitle>
          <CardDescription>Live check against GET /api/v1/health</CardDescription>
        </CardHeader>
        <CardContent>
          {health.isLoading && <p className="text-sm text-muted-foreground">Checking...</p>}
          {health.isError && (
            <p className="text-sm text-destructive">
              {health.error instanceof Error
                ? health.error.message
                : "Could not reach the backend."}
            </p>
          )}
          {health.data && (
            <div className="flex items-center gap-2">
              <Badge variant="accent">{health.data.status}</Badge>
              <span className="text-sm text-muted-foreground">
                {health.data.app_name} · {health.data.app_env}
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Signed in as</CardTitle>
          <CardDescription>Live check against GET /api/v1/identity/me</CardDescription>
        </CardHeader>
        <CardContent>
          {currentUser.isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
          {currentUser.isError && (
            <p className="text-sm text-destructive">Could not load your profile.</p>
          )}
          {currentUser.data && (
            <div className="flex flex-col gap-1">
              <span className="text-sm">{currentUser.data.email}</span>
              <div className="flex gap-1">
                {currentUser.data.roles.map((role) => (
                  <Badge key={role} variant="primary">
                    {role}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
