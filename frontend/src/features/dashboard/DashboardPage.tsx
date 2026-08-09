import { useCurrentUser } from "@/api/queries/auth";
import { useHealthCheck } from "@/api/queries/health";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button-variants";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SystemStatusCard } from "@/features/dashboard/SystemStatusCard";
import { cn } from "@/lib/utils";
import { ClipboardList } from "lucide-react";

// Temporary, not a real feature — a private Artifact page for tracking
// backlog/up-next dev work between sessions, linked here for convenience.
// Remove this card (and the constant) once that tracking moves somewhere
// permanent, or is no longer needed.
const BUILD_QUEUE_URL = "https://claude.ai/code/artifact/4fce51ad-9e84-411b-8cf2-12d382e7a391";

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

      <SystemStatusCard />

      <Card>
        <CardHeader>
          <CardTitle>Build Queue</CardTitle>
          <CardDescription>Backlog and up-next tracker for this project</CardDescription>
        </CardHeader>
        <CardContent>
          <a
            href={BUILD_QUEUE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            <ClipboardList className="h-4 w-4" />
            Open Build Queue
          </a>
        </CardContent>
      </Card>
    </div>
  );
}
