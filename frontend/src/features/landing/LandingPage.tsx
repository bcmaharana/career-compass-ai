import { buttonVariants } from "@/components/ui/button-variants";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { Compass, LineChart, Sparkles, UserCircle, UserPlus, Users } from "lucide-react";
import { Navigate, Link } from "react-router-dom";

/**
 * Public marketing/entry page at "/". Deliberately outside AppShell —
 * the hero CTAs reuse `buttonVariants` from button-variants.ts directly
 * (not the `<Button>` component itself, since these navigate via
 * react-router's `<Link>`, which renders an `<a>`, not a `<button>`) so
 * they get the same transparent-at-rest/rainbow-on-hover treatment as
 * every button inside the app shell (2026-08-09 — an earlier version of
 * this page intentionally opted out of that rule for a bolder,
 * always-visible CTA look; reversed on explicit request).
 *
 * Redirects an already-authenticated visitor straight to /dashboard
 * rather than showing them the pitch again.
 */
export function LandingPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="min-h-screen bg-[hsl(218,25%,93%)]">
      <svg width="0" height="0" className="absolute" aria-hidden="true">
        <defs>
          <linearGradient id="rainbow-accent-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="12.5%" stopColor="#a855f7" />
            <stop offset="37.5%" stopColor="#3b82f6" />
            <stop offset="58.33%" stopColor="#22c55e" />
            <stop offset="75%" stopColor="#fdba74" />
            <stop offset="91.67%" stopColor="#fca5a5" />
          </linearGradient>
        </defs>
      </svg>

      <header className="fixed inset-x-0 top-0 z-20 flex items-center justify-between bg-primary px-6 py-5 shadow-card sm:px-10">
        <div className="flex items-center gap-2">
          <Compass className="h-6 w-6" strokeWidth={2} color="url(#rainbow-accent-gradient)" />
          <span className="font-display text-lg font-semibold text-primary-foreground">
            Career Compass AI
          </span>
        </div>
        <div className="flex items-center gap-1">
          <Tooltip content="Sign up">
            <Link
              to="/signup"
              aria-label="Sign up"
              className="flex h-9 w-9 items-center justify-center rounded-md text-primary-foreground transition-opacity hover:opacity-80"
            >
              <UserPlus className="h-5 w-5" />
            </Link>
          </Tooltip>
          <Tooltip content="Sign in">
            <Link
              to="/login"
              aria-label="Sign in"
              className="flex h-9 w-9 items-center justify-center rounded-md transition-opacity hover:opacity-80"
            >
              <UserCircle className="h-5 w-5" strokeWidth={2} color="url(#rainbow-accent-gradient)" />
            </Link>
          </Tooltip>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 pb-24 pt-[88px] text-center sm:px-10 sm:pt-[104px]">
        {/* Decorative hero graphic — an abstract knowledge-graph motif
            (nodes/edges), thematically tied to the actual CIKG
            (Career Intelligence Knowledge Graph) product rather than a
            generic stock image. Self-contained inline SVG, no external
            image request, reusing the page's own rainbow-accent
            gradient def for the connecting edges. */}
        <div className="mx-auto mb-8 max-w-[403px]" aria-hidden="true">
          <svg viewBox="0 0 600 260" className="h-auto w-full">
            <defs>
              <filter id="hero-graph-glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="14" />
              </filter>
            </defs>
            <circle
              cx="300"
              cy="140"
              r="90"
              fill="url(#rainbow-accent-gradient)"
              opacity="0.3"
              filter="url(#hero-graph-glow)"
            />
            {[
              [410, 140],
              [355, 45],
              [245, 45],
              [190, 140],
              [245, 235],
              [355, 235],
            ].map(([x, y]) => (
              <line
                key={`edge-${x}-${y}`}
                x1="300"
                y1="140"
                x2={x}
                y2={y}
                stroke="url(#rainbow-accent-gradient)"
                strokeWidth="1.5"
                opacity="0.5"
              />
            ))}
            <line x1="410" y1="140" x2="355" y2="45" stroke="url(#rainbow-accent-gradient)" strokeWidth="1" opacity="0.3" />
            <line x1="245" y1="45" x2="190" y2="140" stroke="url(#rainbow-accent-gradient)" strokeWidth="1" opacity="0.3" />
            <line x1="190" y1="140" x2="245" y2="235" stroke="url(#rainbow-accent-gradient)" strokeWidth="1" opacity="0.3" />
            <line x1="355" y1="235" x2="410" y2="140" stroke="url(#rainbow-accent-gradient)" strokeWidth="1" opacity="0.3" />
            <circle cx="300" cy="140" r="16" fill="hsl(var(--primary))" />
            {[
              [410, 140, "#a855f7"],
              [355, 45, "#3b82f6"],
              [245, 45, "#22c55e"],
              [190, 140, "#fdba74"],
              [245, 235, "#fca5a5"],
              [355, 235, "#a855f7"],
            ].map(([x, y, color]) => (
              <circle key={`node-${x}-${y}`} cx={x} cy={y} r="9" fill={color as string} />
            ))}
          </svg>
        </div>

        <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
          Your career, backed by{" "}
          <span className="bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] bg-clip-text text-transparent">
            continuous AI intelligence
          </span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-muted-foreground">
          Build a living career profile, close real skill gaps, and get a governed AI coach in
          your corner — whether you're managing your own path or your whole team's.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            to="/signup?type=individual"
            className={cn(buttonVariants({ variant: "primary", size: "lg" }), "w-full sm:w-auto")}
          >
            Get started for yourself
          </Link>
          <Link
            to="/signup?type=organization"
            className={cn(buttonVariants({ variant: "outline", size: "lg" }), "w-full sm:w-auto")}
          >
            Set up for your team
          </Link>
        </div>

        <div className="mt-10 grid gap-8 text-left sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-card p-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <Users className="h-6 w-6" color="url(#rainbow-accent-gradient)" />
            </div>
            <h3 className="mt-4 font-display font-semibold">One living profile</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Experience, education, certifications, and skills in one place — import from an
              existing resume in minutes.
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <LineChart className="h-6 w-6" color="url(#rainbow-accent-gradient)" />
            </div>
            <h3 className="mt-4 font-display font-semibold">Real gap analysis</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              See exactly which skills stand between you and a target role, grounded in a shared
              knowledge graph, not guesswork.
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <Sparkles className="h-6 w-6" color="url(#rainbow-accent-gradient)" />
            </div>
            <h3 className="mt-4 font-display font-semibold">A governed AI coach</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Every AI recommendation is explainable and auditable — built for individuals and
              enterprises alike.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
