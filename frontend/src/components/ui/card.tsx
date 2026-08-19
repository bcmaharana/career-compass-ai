import { cn } from "@/lib/utils";
import { forwardRef } from "react";
import type { HTMLAttributes } from "react";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        // min-w-0: every career-profile section card is a direct CSS
        // Grid item (CareerProfilePage.tsx's `grid gap-3`), and grid
        // items default to min-width: auto — letting a wide row of
        // content (e.g. a crowded Add/Edit/Clear/Collapse/Move button
        // row) force the card itself wider than its grid track instead
        // of shrinking to fit, rather than truncating/wrapping within
        // it. Harmless where a card already fits its track on its own.
        "min-w-0 rounded-lg border border-border bg-card text-card-foreground",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  // Vertical padding trimmed from the original p-6 (24px) to py-4
  // (16px) — direct user feedback that "main cards" (this shared
  // wrapper, used by every Card on every page) hadn't gotten the same
  // margin reduction already applied to per-item list rows inside them.
  // Horizontal padding (px-6) is deliberately left unchanged, matching
  // every other card-margin fix so far (reduce top/bottom, keep
  // left/right).
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col gap-1.5 px-6 py-4", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={cn(
        // Smaller on mobile than the plain text-lg this used everywhere
        // — card headers there are often crowded with several action
        // buttons (Add/Edit/Clear/Collapse/Move, see the career-profile
        // section cards), squeezing the title into a narrow column where
        // text-lg wraps to two lines and reads as oversized relative to
        // everything around it. md: restores the original text-lg once
        // there's room for it.
        "font-display text-base font-semibold leading-tight md:text-lg",
        className,
      )}
      {...props}
    />
  ),
);
CardTitle.displayName = "CardTitle";

export const CardDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
  ),
);
CardDescription.displayName = "CardDescription";

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  // Bottom padding trimmed from p-6 (24px) to pb-4 (16px), matching
  // CardHeader's own reduction above — top stays 0 (a CardHeader
  // already sits above almost every CardContent) and left/right stay
  // at px-6, unchanged.
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("px-6 pb-4 pt-0", className)} {...props} />
  ),
);
CardContent.displayName = "CardContent";

export const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex items-center px-6 pb-4 pt-0", className)} {...props} />
  ),
);
CardFooter.displayName = "CardFooter";
