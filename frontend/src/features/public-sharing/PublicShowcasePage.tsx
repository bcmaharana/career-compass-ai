import { usePublicShowcasePage } from "@/api/queries/public-sharing";
import type { components } from "@/api/schema.gen";
import { Card, CardContent } from "@/components/ui/card";
import { RichTextDisplay } from "@/components/ui/rich-text-editor";
import { Tooltip } from "@/components/ui/tooltip";
import { PublicPageHeader } from "@/features/public-sharing/PublicPageHeader";
import { useNoIndex } from "@/hooks/useNoIndex";
import { ApiError } from "@/api/client";
import { stripHtml } from "@/lib/strip-html";
import { ExternalLink, UserRound } from "lucide-react";
import { Link, useParams } from "react-router-dom";

type PublicShowcaseRow = components["schemas"]["PublicShowcaseBlock"];
type PublicShowcaseColumn = components["schemas"]["PublicShowcaseColumn"];
type PublicShowcasePageData = components["schemas"]["PublicShowcasePageResponse"];

/** "CAREER PORTFOLIO | " plus the page's own Name/Headline (direct
 * 2026-08-27 request, replacing both the generic "Career Compass AI"
 * brand text and the earlier profile-derived name) — uses exactly what
 * the owner entered in the Showcase Page editor's own Header fields
 * (`page.name`/`page.headline`, falling back to owner_display_name for
 * a page that predates this feature, same fallback ShowcaseTopBar's
 * own heading already uses), not the account/profile name. The
 * headline is flattened to plain text (stripHtml) rather than rendered
 * as rich HTML here — any explicit dark text color the owner applied
 * for display on a light card would be unreadable on this bar's dark
 * navy background. The vertical divider is a real stretched element,
 * not a "|" character, so it always matches the two-line block's
 * actual height regardless of font size. */
function ShowcaseBrandTitle({ page }: { page: PublicShowcasePageData }) {
  const name = page.name || page.owner_display_name;
  const headlineText = page.headline ? stripHtml(page.headline) : "";
  return (
    <div className="flex min-w-0 items-stretch gap-3">
      <span className="shrink-0 self-center whitespace-nowrap font-display text-base font-semibold uppercase tracking-tight text-primary-foreground sm:text-lg">
        Career Portfolio
      </span>
      <div className="w-px shrink-0 self-stretch bg-primary-foreground/40" />
      <div className="flex min-w-0 flex-col justify-center">
        {/* Tooltip (components/ui/tooltip.tsx), not a native `title`
            attribute — reported live as too slow: browsers delay a
            native title tooltip by ~600ms-1s with no way to shorten it
            via CSS/HTML, whereas this app's own Tooltip component shows
            it the instant the mouse enters. `placement="bottom-end"
            wrap`: this trigger is truncated to fill its available width
            right up to the header's own right edge, so the default
            left-anchored, nowrap tooltip (fine for TargetRolesWidget's
            wide row) had nowhere to grow but off-screen for a long
            headline — reported live. bottom-end anchors the tooltip's
            RIGHT edge to the trigger's right edge instead (more open
            space to its left here), and `wrap` bounds it to a
            viewport-relative max-width instead of growing indefinitely. */}
        <Tooltip content={name} className="min-w-0" placement="bottom-end" wrap>
          <p className="truncate text-sm font-semibold text-primary-foreground sm:text-base">
            {name}
          </p>
        </Tooltip>
        {headlineText && (
          <>
            <hr className="my-0.5 border-t border-primary-foreground/30" />
            <Tooltip content={headlineText} className="min-w-0" placement="bottom-end" wrap>
              <p className="truncate text-xs text-primary-foreground/70">{headlineText}</p>
            </Tooltip>
          </>
        )}
      </div>
    </div>
  );
}

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
      <PublicPageHeader>{page && <ShowcaseBrandTitle page={page} />}</PublicPageHeader>
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
            {/* Executive Summary moves into its own card once a
                background image is set — the top bar becomes just the
                image then, with nowhere left to put the summary text
                beside it (direct 2026-08-27 request). Without a
                background image, ShowcaseTopBar itself still shows the
                summary beside the profile photo, unchanged. */}
            {page.background_image_url && page.summary && (
              <Card>
                <CardContent className="py-4">
                  <RichTextDisplay html={page.summary} className="text-sm" />
                </CardContent>
              </Card>
            )}
            {page.blocks.map((row) => (
              <ShowcaseRowView key={row.id} row={row} ownerHandle={page.owner_handle} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

/** Top bar (direct 2026-08-24 request; redesigned 2026-08-27 once Name/
 * Headline moved into the public page's own brand header bar —
 * ShowcaseBrandTitle above): a real background image the owner uploads
 * (ShowcaseHeaderBar's own new "Background Image" control) when set,
 * with the Executive Summary moved into its own card below instead of
 * repeated here; otherwise the original profile-photo + Executive
 * Summary layout, unchanged, minus the now-redundant name/headline.
 * `photo_url` is always resolved fresh from the real Career Profile by
 * the backend, never independent of it ("the profile picture will be
 * fixed" — direct request).
 *
 * The profile photo still overlays the background image on its left
 * side, same position it held in the plain photo+summary layout below
 * (direct 2026-08-27 follow-up: "the profile picture needs to be
 * displayed on top of the background image... the way it was showing
 * before"). Height is deliberately `h-auto` (no crop at all) below the
 * `sm` breakpoint and only becomes a fixed, `object-cover`-cropped
 * banner from `sm` up — a fixed height at every width would crop a
 * portrait-oriented or unusually-shaped image most aggressively on the
 * narrowest (mobile) viewports, exactly the "show the full picture on
 * mobile" case flagged directly. */
function ShowcaseTopBar({ page }: { page: PublicShowcasePageData }) {
  if (page.background_image_url) {
    return (
      <div className="relative w-full overflow-hidden rounded-md border border-border">
        <img
          src={page.background_image_url}
          alt=""
          className="h-auto w-full object-cover sm:h-64"
        />
        {/* Ring: a `box-shadow`, not a `border` — box-shadow is computed
            independently of the image's own content-clip, whereas a
            `border` shares the same box-model computation as that clip
            (the likely source of an earlier, real "uneven ring"
            complaint against a border-based version of this). Zoom:
            `background-image`/`background-size`/`background-position`
            on this fixed-size div, NOT `object-fit` + `transform:
            scale()` on an `<img>` — a `transform: scale()` visually
            grows the element PAST its own laid-out box (that's how the
            earlier version's face-zoom worked), and that overflow was
            getting clipped by this banner's own `overflow-hidden`,
            reported live as the avatar looking "cut out a little on
            the left and more on the bottom." `background-size`/
            `-position` achieve the identical zoom-and-pan crop entirely
            WITHIN the div's own fixed box — nothing can ever bleed past
            its edges, so there's nothing left for the ancestor to clip.
            125% + "center top" biases the crop toward the face
            (confirmed against the real photo here: 1234x1274, face
            sitting in the upper half, more shoulder/chest below it than
            headroom above — object-fit:cover alone barely crops a
            near-square photo like this at all, leaving no real
            "camera") — 125px on desktop maps directly to `h`/`w` now,
            no compounding scale factor to divide out (a real mistake in
            the transform-based version: "increase to 140px" then
            rendered at 175px, since the old scale-125 multiplied
            whatever base size was set). Mobile size left unchanged. */}
        <div className="absolute bottom-3 left-3 sm:bottom-4 sm:left-4">
          {page.photo_url ? (
            <div
              className="h-20 w-20 rounded-full bg-top bg-no-repeat shadow-[0_0_0_2px_hsl(var(--card)),0_2px_6px_rgba(0,0,0,0.35)] sm:h-[125px] sm:w-[125px]"
              style={{ backgroundImage: `url(${page.photo_url})`, backgroundSize: "125%" }}
            />
          ) : (
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-card text-muted-foreground shadow-[0_0_0_2px_hsl(var(--card)),0_2px_6px_rgba(0,0,0,0.35)] sm:h-[125px] sm:w-[125px]">
              <UserRound className="h-8 w-8" />
            </div>
          )}
        </div>
      </div>
    );
  }
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
      <div className="flex min-w-0 flex-1 flex-col justify-center gap-1">
        {page.summary && <RichTextDisplay html={page.summary} className="text-sm" />}
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
