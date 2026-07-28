import { QueryClient } from "@tanstack/react-query";

/**
 * Single QueryClient instance for the whole app. Lives in its own module
 * (rather than only inside App.tsx) so non-component code — like
 * api/client.ts's 401 handler — can clear the cache too, not just
 * React components via useQueryClient().
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
