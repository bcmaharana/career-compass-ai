import { ApiError } from "@/api/client";
import { usePublicArticle } from "@/api/queries/public-sharing";
import { Card, CardContent } from "@/components/ui/card";
import { RichTextDisplay } from "@/components/ui/rich-text-editor";
import { PublicPageHeader } from "@/features/public-sharing/PublicPageHeader";
import { useNoIndex } from "@/hooks/useNoIndex";
import { useParams } from "react-router-dom";

/**
 * Anonymous, read-only route at `/:handle/article/:key` — the public
 * framing of an Interview Prep Topic once its owner toggles it public.
 * Registered as a top-level route (router.tsx), NOT nested under
 * ProtectedRoute/AppShell. Only `:key` is ever sent to the backend.
 */
export function PublicArticlePage() {
  useNoIndex();
  const { key } = useParams<{ key: string }>();
  const { data: article, isLoading, isError, error } = usePublicArticle(key);

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

            {article.image_url && (
              <img
                src={article.image_url}
                alt=""
                className="max-h-[75vh] w-full max-w-2xl rounded-md border border-border object-contain"
              />
            )}

            {article.discussion && (
              <Card>
                <CardContent className="py-4">
                  <RichTextDisplay html={article.discussion} />
                </CardContent>
              </Card>
            )}

            {article.reference_links.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Reference Links
                </p>
                <ul className="flex flex-col gap-1">
                  {article.reference_links.map((link, i) => (
                    <li key={`${link.url}-${i}`}>
                      <a
                        href={link.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
