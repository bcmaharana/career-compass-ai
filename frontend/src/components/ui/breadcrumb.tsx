import { PLATFORM_BASE_URL } from "@/lib/platform";
import { cn } from "@/lib/utils";
import { Fragment } from "react";
import { Link } from "react-router-dom";

export interface BreadcrumbSegment {
  label: string;
  /** Omitted (or on the last segment) — not a link, this is where you
   * are. An absolute URL (starts with "http") renders a plain `<a>`
   * (crossing to another product's own origin); anything else renders a
   * react-router `<Link>`. */
  href?: string;
}

/**
 * Layer-1/layer-2/layer-3 navigation trail — "Hub" is always the first
 * segment (prepended here, not by callers), linking out to the platform's
 * own base URL. Every caller supplies just its own segments (see
 * getBreadcrumbTrail in lib/nav-items.ts for the authenticated-app shape).
 *
 * Two color variants since this renders on both dark headers (AppHeader,
 * LandingPage — primary-colored background, needs primary-foreground
 * tokens for contrast) and light ones (LegalPageLayout — needs the app's
 * normal muted-foreground/foreground tokens instead) — not a single
 * hardcoded color scheme.
 */
export function Breadcrumb({
  segments,
  variant = "light",
  className,
}: {
  segments: BreadcrumbSegment[];
  variant?: "light" | "dark";
  className?: string;
}) {
  const full: BreadcrumbSegment[] = [{ label: "Hub", href: PLATFORM_BASE_URL }, ...segments];
  const linkClass =
    variant === "dark"
      ? "text-primary-foreground/70 hover:text-primary-foreground hover:underline"
      : "text-muted-foreground hover:text-foreground hover:underline";
  const currentClass = variant === "dark" ? "text-primary-foreground/90" : "text-foreground";
  const separatorClass = variant === "dark" ? "text-primary-foreground/40" : "text-muted-foreground/50";

  return (
    <nav aria-label="Breadcrumb" className={cn("flex min-w-0 items-center gap-1 text-xs", className)}>
      {full.map((segment, index) => {
        const isLast = index === full.length - 1;
        const isExternal = segment.href?.startsWith("http");
        return (
          <Fragment key={`${segment.label}-${index}`}>
            {index > 0 && (
              <span aria-hidden="true" className={separatorClass}>
                /
              </span>
            )}
            {segment.href && !isLast ? (
              isExternal ? (
                <a href={segment.href} className={cn("shrink-0", linkClass)}>
                  {segment.label}
                </a>
              ) : (
                <Link to={segment.href} className={cn("shrink-0", linkClass)}>
                  {segment.label}
                </Link>
              )
            ) : (
              <span className={cn("truncate", isLast ? currentClass : linkClass)}>{segment.label}</span>
            )}
          </Fragment>
        );
      })}
    </nav>
  );
}
