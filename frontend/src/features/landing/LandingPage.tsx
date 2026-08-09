import { useAuthStore } from "@/stores/auth-store";
import { Compass, LineChart, Sparkles, Users } from "lucide-react";
import { Navigate, Link } from "react-router-dom";

/**
 * Public marketing/entry page at "/". Deliberately outside AppShell and
 * outside the center-pane button-styling rule (see button-variants.ts) —
 * this page needs solid, high-contrast hero CTAs the way LoginPage's card
 * already does, not the transparent-until-hover pattern used once inside
 * the authenticated app shell.
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
    <div className="min-h-screen bg-background">
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

      <header className="flex items-center justify-between px-6 py-5 sm:px-10">
        <div className="flex items-center gap-2">
          <Compass className="h-6 w-6" strokeWidth={2} color="url(#rainbow-accent-gradient)" />
          <span className="font-display text-lg font-semibold">Career Compass AI</span>
        </div>
        <Link
          to="/login"
          className="rounded-md px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          Log in
        </Link>
      </header>

      <main className="mx-auto max-w-4xl px-6 pb-24 pt-12 text-center sm:px-10 sm:pt-20">
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
            className="w-full rounded-lg bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] px-6 py-3 text-center text-sm font-semibold text-white shadow-card transition-transform hover:scale-[1.02] sm:w-auto"
          >
            Get started for yourself
          </Link>
          <Link
            to="/signup?type=organization"
            className="w-full rounded-lg border border-border px-6 py-3 text-center text-sm font-semibold text-foreground transition-colors hover:border-transparent hover:bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] hover:text-white sm:w-auto"
          >
            Set up for your team
          </Link>
        </div>

        <div className="mt-20 grid gap-8 text-left sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-card p-6">
            <Users className="h-6 w-6" color="url(#rainbow-accent-gradient)" />
            <h3 className="mt-4 font-display font-semibold">One living profile</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Experience, education, certifications, and skills in one place — import from an
              existing resume in minutes.
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-6">
            <LineChart className="h-6 w-6" color="url(#rainbow-accent-gradient)" />
            <h3 className="mt-4 font-display font-semibold">Real gap analysis</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              See exactly which skills stand between you and a target role, grounded in a shared
              knowledge graph, not guesswork.
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-6">
            <Sparkles className="h-6 w-6" color="url(#rainbow-accent-gradient)" />
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
