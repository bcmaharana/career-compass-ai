import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useQuery } from "@tanstack/react-query";

type PublicShowcasePageResponse = components["schemas"]["PublicShowcasePageResponse"];
type PublicArticleResponse = components["schemas"]["PublicArticleResponse"];

/**
 * Anonymous reads — no Authorization header is attached (apiClient
 * only adds one when the in-memory auth store actually holds a token;
 * these hooks are only ever used from the two public pages, which
 * render outside ProtectedRoute/AppShell and therefore never have one).
 * `retry: false` — a 404 here means "doesn't exist or isn't public
 * right now," not a transient failure worth retrying.
 */
export function usePublicShowcasePage(shareKey: string | undefined) {
  return useQuery({
    queryKey: ["public-showcase-page", shareKey],
    queryFn: () =>
      apiClient.get<PublicShowcasePageResponse>(`/api/v1/public/showcase-pages/${shareKey}`),
    enabled: !!shareKey,
    retry: false,
  });
}

export function usePublicArticle(shareKey: string | undefined) {
  return useQuery({
    queryKey: ["public-article", shareKey],
    queryFn: () => apiClient.get<PublicArticleResponse>(`/api/v1/public/articles/${shareKey}`),
    enabled: !!shareKey,
    retry: false,
  });
}
