import { ApiError } from "@/api/client";
import { usePublicArticle } from "@/api/queries/public-sharing";
import type { components } from "@/api/schema.gen";
import { Card, CardContent } from "@/components/ui/card";
import { RichTextDisplay } from "@/components/ui/rich-text-editor";
import { PublicPageHeader } from "@/features/public-sharing/PublicPageHeader";
import { useNoIndex } from "@/hooks/useNoIndex";
import { ExternalLink } from "lucide-react";
import { Link, useParams } from "react-router-dom";

type PublicArticleRow = components["schemas"]["PublicArticleBlock"];
type PublicArticleColumn = components["schemas"]["PublicArticleColumn"];

/**
 * Anonymous, read-only route at `/:handle/article/:key` — the public
 * framing of an Interview Prep Topic once its owner toggles it public.
 * Registered as a top-level route (router.tsx), NOT nested under
 * ProtectedRoute/AppShell. Only `:key` is ever sent to the backend.
 *
 * Content is a freeform blocks document (2026-08-24 — Articles moved
 * from a fixed discussion/image/reference_links shape to the same
 * row/column content-block model Showcase Page uses), rendered the same
 * "each row's columns side by side on desktop, stacked on mobile" way
 * PublicShowcasePage.tsx's own ShowcaseRowView already establishes.
 */
export function PublicArticlePage() {
  useNoIndex();
  const { key } = useParams<{ key: string }>();
  const { data: article, isLoading, isError, error } = usePublicArticle(key);

  return (
    <div className="min-h-screen bg-[hsl(218,25%,93%)]">
      <PublicPageHeader />
      {/* Same width treatment as PublicShowcasePage.tsx — see that file's
          comment for the full "why" (mobile unchanged, genuine 80% width
          from `md` up). */}
      <main className="mx-auto max-w-2xl px-6 py-10 sm:px-10 md:w-4/5 md:max-w-none">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {isError && (
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-sm text-muted-foreground">
                {error instanceof ApiError && error.status === 404
                  ? "This article doesn't exist or is no longer public."
                  : "Something went wrong loading this article."}
              </p>
            </CardContent>
          </Card>
        )}
        {article && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <h1 className="font-display text-2xl font-semibold text-foreground">
                {article.name}
              </h1>
              <p className="text-sm text-muted-foreground">By {article.owner_display_name}</p>
            </div>
            {article.blocks.map((row) => (
              <ArticleRowView key={row.id} row={row} ownerHandle={article.owner_handle} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

/** Each row renders its columns side by side (equal width) on desktop
 * and stacked vertically on mobile — same convention
 * PublicShowcasePage.tsx's own ShowcaseRowView establishes. A 1-column
 * row (every Article migrated from the old fixed shape) is visually
 * identical to the old single-section layout. */
function ArticleRowView({ row, ownerHandle }: { row: PublicArticleRow; ownerHandle: string }) {
  return (
    <div className="flex flex-col gap-4 md:flex-row">
      {row.columns.map((column) => (
        <Card key={column.id} className="min-w-0 flex-1 basis-0">
          <CardContent className="flex flex-col gap-2 py-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {column.label}
            </p>
            <ArticleColumnContent column={column} ownerHandle={ownerHandle} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ArticleColumnContent({
  column,
  ownerHandle,
}: {
  column: PublicArticleColumn;
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
