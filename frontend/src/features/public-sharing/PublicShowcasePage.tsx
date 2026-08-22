import { usePublicShowcasePage } from "@/api/queries/public-sharing";
import type { components } from "@/api/schema.gen";
import { Card, CardContent } from "@/components/ui/card";
import { RichTextDisplay } from "@/components/ui/rich-text-editor";
import { PublicPageHeader } from "@/features/public-sharing/PublicPageHeader";
import { useNoIndex } from "@/hooks/useNoIndex";
import { ApiError } from "@/api/client";
import { ExternalLink } from "lucide-react";
import { Link, useParams } from "react-router-dom";

type PublicShowcaseBlock = components["schemas"]["PublicShowcaseBlock"];

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
      <main className="mx-auto max-w-2xl px-6 py-10 sm:px-10">
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
            <div className="flex flex-col gap-1">
              <h1 className="font-display text-2xl font-semibold text-foreground">
                {page.owner_display_name}
              </h1>
              <p className="text-sm text-muted-foreground">{page.role_name}</p>
            </div>
            {page.blocks.map((block) => (
              <ShowcaseBlockView key={block.id} block={block} ownerHandle={page.owner_handle} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function ShowcaseBlockView({
  block,
  ownerHandle,
}: {
  block: PublicShowcaseBlock;
  ownerHandle: string;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2 py-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {block.label}
        </p>
        <ShowcaseBlockContent block={block} ownerHandle={ownerHandle} />
      </CardContent>
    </Card>
  );
}

function ShowcaseBlockContent({
  block,
  ownerHandle,
}: {
  block: PublicShowcaseBlock;
  ownerHandle: string;
}) {
  switch (block.type) {
    case "rich_text":
      return block.html ? <RichTextDisplay html={block.html} /> : null;
    case "image":
      return block.image_url ? (
        <img
          src={block.image_url}
          alt=""
          className="max-h-[75vh] w-full max-w-2xl rounded-md border border-border object-contain"
        />
      ) : null;
    case "video_embed":
      return block.video_embed_url ? (
        <div className="aspect-video w-full overflow-hidden rounded-md border border-border">
          <iframe
            src={block.video_embed_url}
            title={block.label}
            className="h-full w-full"
            allowFullScreen
          />
        </div>
      ) : null;
    case "external_link":
      return block.external_url ? (
        <a
          href={block.external_url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          {block.external_url}
        </a>
      ) : null;
    case "article_link":
      return block.article_share_key ? (
        <Link
          to={`/${ownerHandle}/article/${block.article_share_key}`}
          className="text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
        >
          Read the full article &rarr;
        </Link>
      ) : (
        <p className="text-sm text-muted-foreground">{block.label}</p>
      );
  }
}
