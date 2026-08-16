import { cn } from "@/lib/utils";
import { forwardRef } from "react";
import { Link, type LinkProps } from "react-router-dom";

/**
 * A link embedded inside a sentence/paragraph of body text — as opposed
 * to nav chrome (rail items, header/footer icon buttons, the logo) or a
 * button-styled `<Link className={buttonVariants(...)}>`, neither of
 * which needs this: both already read as interactive on their own.
 *
 * One consistent style everywhere an inline link appears (accent color
 * + underline, at rest, not just on hover) so a reader can tell it's a
 * link without having to hunt for it or hover every word first — plain
 * `text-muted-foreground hover:text-foreground` (no color/underline
 * distinction from surrounding text until hover) and
 * `text-accent hover:underline` (color alone, no underline until
 * hover) were both in use across the app before this and neither
 * reads as clearly clickable at a glance.
 */
export const InlineLink = forwardRef<HTMLAnchorElement, LinkProps>(
  ({ className, ...props }, ref) => (
    <Link
      ref={ref}
      className={cn(
        "font-medium text-accent underline underline-offset-2 hover:text-accent/80",
        className,
      )}
      {...props}
    />
  ),
);
InlineLink.displayName = "InlineLink";
