import { Compass } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/** Single source of truth for the contact address shown across the
 * Terms of Service and Privacy Policy — a dedicated support address,
 * not a personal one, and defined once here rather than duplicated at
 * every mailto: link so it only needs updating in one place. */
export const CONTACT_EMAIL = "support@scaledbrain.com";

interface LegalPageLayoutProps {
  title: string;
  effectiveDate: string;
  summary: ReactNode;
  children: ReactNode;
}

/**
 * Shared chrome for /terms and /privacy — a plain, readable content
 * page rather than the branded auth-flow treatment (rainbow gradient
 * defs, centered Card) those pages use, since this is a long-form
 * document meant to be read and referenced, not a small interactive
 * form. No typography plugin is installed in this project, so section
 * spacing/type scale is hand-styled here with plain Tailwind utilities
 * rather than a `prose` class.
 */
export function LegalPageLayout({ title, effectiveDate, summary, children }: LegalPageLayoutProps) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border">
        <div className="container flex items-center justify-between py-4">
          <Link to="/" className="flex items-center gap-2 text-foreground">
            <Compass className="h-5 w-5 text-accent" strokeWidth={2} />
            <span className="font-display text-sm font-semibold">Career Compass AI</span>
          </Link>
          <Link to="/signup" className="text-sm text-muted-foreground hover:text-foreground">
            Back to sign up
          </Link>
        </div>
      </header>

      <main className="container max-w-3xl py-10">
        <h1 className="font-display text-3xl font-semibold text-foreground">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Effective {effectiveDate}</p>

        <div className="mt-6 rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">Plain-language summary</p>
          <div className="mt-2 space-y-2">{summary}</div>
        </div>

        <div className="prose-legal mt-8 space-y-8 text-sm leading-relaxed text-foreground">
          {children}
        </div>

        <footer className="mt-12 border-t border-border pt-6 text-sm text-muted-foreground">
          <p>
            Questions about this document? Contact us at{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-foreground underline">
              {CONTACT_EMAIL}
            </a>
            .
          </p>
        </footer>
      </main>
    </div>
  );
}

/** Section heading used throughout both documents — kept as a small
 * shared component so the two pages can't drift out of sync on heading
 * style. */
export function LegalSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="font-display text-lg font-semibold text-foreground">{title}</h2>
      <div className="mt-2 space-y-3">{children}</div>
    </section>
  );
}
