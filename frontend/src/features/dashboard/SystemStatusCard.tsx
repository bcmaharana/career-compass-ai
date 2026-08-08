import { useModelSelection } from "@/api/queries/ai-platform";
import { useSystemStatus } from "@/api/queries/system-status";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyButton } from "@/components/ui/copy-button";
import { RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";

type ServiceStatus = components["schemas"]["ServiceStatusResponse"];
type RateLimitInfo = components["schemas"]["RateLimitInfoResponse"];

function statusBadgeVariant(status: string): "accent" | "destructive" | "default" {
  if (status === "up") return "accent";
  if (status === "down") return "destructive";
  return "default"; // not_configured
}

function statusLabel(status: string): string {
  if (status === "up") return "Up";
  if (status === "down") return "Down";
  return "Not configured";
}

/** <20% remaining reads as a warning color, otherwise plain muted text. */
function usageBarClass(remaining: number, limit: number): string {
  const fraction = limit > 0 ? remaining / limit : 1;
  return fraction < 0.2 ? "bg-destructive" : "bg-accent";
}

function UsageBar({
  label,
  remaining,
  limit,
  resetsIn,
}: {
  label: string;
  remaining: number;
  limit: number;
  resetsIn: string | null;
}) {
  const fraction = limit > 0 ? Math.min(1, Math.max(0, remaining / limit)) : 0;
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {label}: {remaining.toLocaleString()} / {limit.toLocaleString()}
        </span>
        {resetsIn && <span>resets in {resetsIn}</span>}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full ${usageBarClass(remaining, limit)}`}
          style={{ width: `${fraction * 100}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Groq-only today (`rate_limit` is generic on ServiceStatusResponse but
 * only the Groq checker ever populates it — see checkers.py). Reflects
 * whatever groq_provider.py captured off the headers of the last real
 * chat-completion call this backend process made; there is deliberately
 * no live poll here (same reasoning check_groq already had for not
 * spending quota just to prove reachability), so this is empty until
 * the next real Groq call happens, and resets to empty on a backend
 * restart since the snapshot is in-memory only.
 */
function GroqUsage({ rateLimit }: { rateLimit: RateLimitInfo | null | undefined }) {
  if (!rateLimit) {
    return (
      <p className="text-xs text-muted-foreground">
        No usage data yet this session — check back after your next Groq request.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-1.5 pt-0.5">
      {rateLimit.limit_requests != null && rateLimit.remaining_requests != null && (
        <UsageBar
          label="Requests today"
          remaining={rateLimit.remaining_requests}
          limit={rateLimit.limit_requests}
          resetsIn={rateLimit.reset_requests}
        />
      )}
      {rateLimit.limit_tokens != null && rateLimit.remaining_tokens != null && (
        <UsageBar
          label="Tokens this minute"
          remaining={rateLimit.remaining_tokens}
          limit={rateLimit.limit_tokens}
          resetsIn={rateLimit.reset_tokens}
        />
      )}
    </div>
  );
}

function ServiceRow({ service }: { service: ServiceStatus }) {
  return (
    <div className="flex flex-col gap-1 border-b border-border py-2 last:border-0 last:pb-0">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{service.label}</span>
        <Badge variant={statusBadgeVariant(service.status)}>{statusLabel(service.status)}</Badge>
      </div>
      {service.status !== "up" && (
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">{service.detail}</span>
          {service.fix_command && (
            <CopyButton text={service.fix_command} label="Copy fix" className="h-7 shrink-0" />
          )}
        </div>
      )}
      {service.name === "groq" && service.status === "up" && (
        <GroqUsage rateLimit={service.rate_limit} />
      )}
    </div>
  );
}

/**
 * Reuses the same GET /api/v1/ai-platform/models call Settings > AI
 * Model is built on (useModelSelection) — no new backend endpoint
 * needed, this is purely "which one of those already-fetched options
 * is currently selected." Surfaced here because model choice directly
 * explains extraction-quality issues (a real one, this session: a weak
 * local model produced malformed structured output) — this is where a
 * user is likeliest to be diagnosing exactly that.
 */
function ActiveModelRow() {
  const { data: selection, isLoading, isError } = useModelSelection();
  const active = selection?.available.find((option) => option.id === selection.selected_id);

  return (
    <div className="flex flex-col gap-1 border-b border-border pb-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">Active AI Model</span>
        <Link to="/settings/ai-model" className="text-xs text-accent hover:underline">
          Change
        </Link>
      </div>
      {isLoading && <p className="text-xs text-muted-foreground">Loading...</p>}
      {isError && <p className="text-xs text-destructive">Could not load model selection.</p>}
      {active && (
        <div className="flex items-center gap-1.5">
          <Badge variant="accent">{active.display_name}</Badge>
          <span className="text-xs text-muted-foreground">
            {active.provider} · {active.is_default ? "platform default" : "your choice"}
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * Status-only — no service is ever restarted from here. Restarting
 * Postgres/Redis/MinIO/the backend itself would require mounting the
 * Docker socket into the backend container (effectively root on the
 * host), and Ollama runs on the host outside Docker Compose entirely,
 * so the backend has no path to restart it at all. Both explicit,
 * confirmed product decisions (see SystemStatusService's docstring) —
 * "one click" here means one click to copy the exact fix command, not
 * remote execution.
 */
export function SystemStatusCard() {
  const { data, isLoading, isError, refetch, isFetching } = useSystemStatus();

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>System Status</CardTitle>
          <CardDescription>Live check against GET /api/v1/system-status</CardDescription>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => refetch()}
          disabled={isFetching}
          aria-label="Refresh system status"
        >
          <RefreshCw className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <ActiveModelRow />
        {isLoading && <p className="text-sm text-muted-foreground">Checking...</p>}
        {isError && (
          <p className="text-sm text-destructive">Could not reach the status endpoint.</p>
        )}
        {data && (
          <div className="flex flex-col">
            {data.services.map((service) => (
              <ServiceRow key={service.name} service={service} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
