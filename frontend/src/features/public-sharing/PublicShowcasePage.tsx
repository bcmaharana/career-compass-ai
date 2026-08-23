import { usePublicShowcasePage } from "@/api/queries/public-sharing";
import type { components } from "@/api/schema.gen";
import { Card, CardContent } from "@/components/ui/card";
import { RichTextDisplay } from "@/components/ui/rich-text-editor";
import { PublicPageHeader } from "@/features/public-sharing/PublicPageHeader";
import { useNoIndex } from "@/hooks/useNoIndex";
import { ApiError } from "@/api/client";
import { ExternalLink, UserRound } from "lucide-react";
import { Link, useParams } from "react-router-dom";

type PublicShowcaseRow = components["schemas"]["PublicShowcaseBlock"];
type PublicShowcaseColumn = components["schemas"]["PublicShowcaseColumn"];

/**
 * Anonymous, read-only route at `/:handle/:roleTag/:key` — registered
 * as a top-level route (router.tsx), NOT nested under
 * ProtectedRoute/AppShell. Only `:key` is ever sent to the backend
 * (see usePublicShowcasePage); `:handle`/`:roleTag` are cosmetic.
 */
export function PublicShowcasePage() {
  useNoIndex();
  const { key } = useParams<{ key: string }>();
  const { data: page, isLoading, isError, error } = usePublicShowcasePage(key);

  return (
    <div className="min-h-screen bg-[hsl(218,25%,93%)]">
      <PublicPageHeader />
      {/* Mobile stays a comfortable reading column (max-w-2xl, effectively
          full-width minus padding on any real phone anyway). From `md` up
          — this app's own mobile/desktop split, see globals.css — widens
          to a genuine 80% of the viewport (direct 2026-08-24 report: the
          page read as unnecessarily narrow for a recruiter viewing it on
          a real monitor). `md:max-w-none` cancels the mobile max-w-2xl
          cap, which would otherwise still win over w-4/5 above 672px. */}
      <main className="mx-auto max-w-2xl px-6 py-10 sm:px-10 md:w-4/5 md:max-w-none">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {isError && (
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-sm text-muted-foreground">
                {error instanceof ApiError && error.status === 404
                  ? "This page doesn't exist or is no longer public."
                  : "Something went wrong loading this page."}
              </p>
            </CardContent>
          </Card>
        )}
        {page && (
          <div className="flex flex-col gap-4">
            <ShowcaseTopBar page={page} />
            {page.blocks.map((row) => (
              <ShowcaseRowView key={row.id} row={row} ownerHandle={page.owner_handle} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

type PublicShowcasePageData = components["schemas"]["PublicShowcasePageResponse"];

/** Top bar (direct 2026-08-24 request): profile picture on the left,
 * name + headline and the Executive Summary on the right — the
 * read-only counterpart to ShowcasePageSection.tsx's own
 * ShowcaseHeaderBar. `name` falls back to the real, live
 * owner_display_name for the rare case a page predates this feature and
 * hasn't been backfilled/edited yet; `photo_url` is always resolved
 * fresh from the real Career Profile by the backend, never independent
 * of it ("the profile picture will be fixed" — direct request). */
function ShowcaseTopBar({ page }: { page: PublicShowcasePageData }) {
  const name = page.name || page.owner_display_name;
  return (
    <div className="flex flex-col gap-3 rounded-md border border-border bg-card p-4 md:flex-row">
      <div className="flex shrink-0 justify-center md:justify-start">
        {page.photo_url ? (
          <img
            src={page.photo_url}
            alt=""
            className="h-24 w-24 rounded-full border border-border object-cover"
          />
        ) : (
          <div className="flex h-24 w-24 items-center justify-center rounded-full border border-dashed border-border text-muted-foreground">
            <UserRound className="h-8 w-8" />
          </div>
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <h1 className="font-display text-2xl font-semibold text-foreground">{name}</h1>
        {page.headline && (
          <RichTextDisplay html={page.headline} className="mt-1 text-sm text-muted-foreground" />
        )}
        {page.summary && <RichTextDisplay html={page.summary} className="mt-1 text-sm" />}
      </div>
    </div>
  );
}

/** Each row renders its columns side by side (equal width) on desktop
 * and stacked vertically on mobile — same convention the editor's own
 * ShowcaseRowCard establishes. A 1-column row (everything created
 * before multi-column support existed) is visually identical to the
 * old single-block layout. */
function ShowcaseRowView({ row, ownerHandle }: { row: PublicShowcaseRow; ownerHandle: string }) {
  return (
    <div className="flex flex-col gap-4 md:flex-row">
      {row.columns.map((column) => (
        <Card key={column.id} className="min-w-0 flex-1 basis-0">
          <CardContent className="flex flex-col gap-2 py-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {column.label}
            </p>
            <ShowcaseColumnContent column={column} ownerHandle={ownerHandle} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ShowcaseColumnContent({
  column,
  ownerHandle,
}: {
  column: PublicShowcaseColumn;
  ownerHandle: string;
}) {
  switch (column.type) {
    case "rich_text":
      return column.html ? <RichTextDisplay html={column.html} /> : null;
    case "image":
      return column.image_url ? (
        <img
          src={column.image_url}
          alt=""
          className="max-h-[75vh] w-full rounded-md border border-border object-contain"
        />
      ) : null;
    case "video_embed":
      return column.video_embed_url ? (
        <div className="aspect-video w-full overflow-hidden rounded-md border border-border">
          <iframe
            src={column.video_embed_url}
            title={column.label}
            className="h-full w-full"
            allowFullScreen
          />
        </div>
      ) : null;
    case "external_link":
      return column.external_url ? (
        <a
          href={column.external_url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          {column.external_url}
        </a>
      ) : null;
    case "article_link":
      return column.article_share_key ? (
        <Link
          to={`/${ownerHandle}/article/${column.article_share_key}`}
          className="text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
        >
          Read the full article &rarr;
        </Link>
      ) : (
        <p className="text-sm text-muted-foreground">{column.label}</p>
      );
  }
}
