import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useQuery } from "@tanstack/react-query";

type SystemStatusResponse = components["schemas"]["SystemStatusResponse"];

/**
 * Dashboard System Status widget. Polls GET /api/v1/system-status on an
 * interval so the widget self-updates (e.g. after the user runs a fix
 * command and comes back to check) without requiring a manual refresh —
 * React Query's own `refetch()` (returned here) also backs an explicit
 * "Refresh" button for instant feedback. Status-only: this never
 * triggers any server-side restart, see SystemStatusService's docstring
 * (backend/app/application/system_status/system_status_service.py) for
 * why.
 */
export function useSystemStatus() {
  return useQuery({
    queryKey: ["system-status"],
    queryFn: () => apiClient.get<SystemStatusResponse>("/api/v1/system-status"),
    refetchInterval: 15_000,
  });
}
