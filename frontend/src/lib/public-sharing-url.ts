/**
 * Builds the pretty public-sharing URL for a Showcase Page or Article.
 *
 * The `:handle`/`:roleTag` path segments are purely cosmetic — the
 * backend's anonymous endpoints (`GET /api/v1/public/showcase-pages/{key}`
 * / `GET /api/v1/public/articles/{key}`) only ever look at the trailing
 * `:key` segment (see PublicShowcaseService's own docstring: "the
 * pretty URL and the API are decoupled"). `handle`/`roleTag` fall back
 * to a plain placeholder when not yet known (e.g. the viewer's handle
 * hasn't loaded yet) — the link still resolves correctly either way,
 * it just won't look as polished until the real values are available.
 */
export function publicShowcasePageUrl(
  handle: string | null | undefined,
  roleTag: string,
  shareKey: string,
): string {
  return `${window.location.origin}/${handle || "me"}/${roleTag}/${shareKey}`;
}

export function publicArticleUrl(handle: string | null | undefined, shareKey: string): string {
  return `${window.location.origin}/${handle || "me"}/article/${shareKey}`;
}
