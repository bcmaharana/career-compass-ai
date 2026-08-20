import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * "Back to Settings" link shown above every Settings sub-page's own
 * card — direct 2026-08-20 request. Same visual pattern LoginPage.tsx's
 * own "Back to home" link already uses (ArrowLeft icon + muted text,
 * not InlineLink's always-underlined body-text style, which reads wrong
 * sitting above a card rather than embedded in a sentence).
 *
 * Deliberately not rendered on SettingsLandingPage itself — that page
 * IS "Settings," there's nowhere further back to offer within this
 * section. The Right Nav's Settings sub-nav remains the other way to
 * move between sub-pages on desktop; this is specifically for getting
 * back to the landing page/category chooser, including on mobile where
 * the Right Nav doesn't render at all.
 */
export function SettingsBackLink() {
  return (
    <Link
      to="/settings"
      className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" />
      Back to Settings
    </Link>
  );
}
