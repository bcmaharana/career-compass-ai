import { buttonVariants } from "@/components/ui/button-variants";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { Compass, LineChart, Sparkles, UserCircle, UserPlus, Users } from "lucide-react";
import { Navigate, Link } from "react-router-dom";

// Sri Yantra hero graphic — replaced the earlier abstract hexagonal
// hub-and-spoke "knowledge graph" motif on explicit request. Built from
// 9 interlocking isoceles triangles (4 "Shiva" pointing up, 5 "Shakti"
// pointing down, each with its apex on the vertical center axis — the
// actual defining construction of a Sri Yantra), a central bindu point,
// two boundary circles, and a ring of lotus petals. Not a ritually
// exact reconstruction — real yantras follow empirical proportions with
// no simple closed-form formula (see Kulaichev's geometric analysis of
// the figure) — this is a decorative approximation tuned by eye at this
// hero graphic's scale, deliberately kept to triangles/circles/petals
// without the outer square gates (bhupura) to stay visually clean
// rather than maximalist next to the animated background dots. Reuses
// the page's own rainbow-accent gradient for every stroke, same as the
// motif it replaced, so the rest of the page's visual language (dots,
// buttons, headings) is untouched.
const YANTRA_CX = 300;
const YANTRA_CY = 140;
const YANTRA_R = 95;

interface YantraTriangleSpec {
  dir: "up" | "down";
  apex: number; // distance from center to the apex, as a fraction of YANTRA_R
  base: number; // distance from center to the base (opposite side), as a fraction of YANTRA_R
  halfWidth: number; // half the base width, as a fraction of YANTRA_R
}

// 4 upward ("Shiva") triangles, largest to smallest.
const YANTRA_UP: YantraTriangleSpec[] = [
  { dir: "up", apex: 1.0, base: 0.74, halfWidth: 0.96 },
  { dir: "up", apex: 0.78, base: 0.5, halfWidth: 0.7 },
  { dir: "up", apex: 0.52, base: 0.26, halfWidth: 0.46 },
  { dir: "up", apex: 0.26, base: 0.04, halfWidth: 0.2 },
];
// 5 downward ("Shakti") triangles, largest to smallest.
const YANTRA_DOWN: YantraTriangleSpec[] = [
  { dir: "down", apex: 0.94, base: 0.68, halfWidth: 0.9 },
  { dir: "down", apex: 0.7, base: 0.44, halfWidth: 0.64 },
  { dir: "down", apex: 0.46, base: 0.22, halfWidth: 0.4 },
  { dir: "down", apex: 0.22, base: 0.06, halfWidth: 0.16 },
  { dir: "down", apex: 0.06, base: 0.02, halfWidth: 0.05 },
];
const YANTRA_TRIANGLES = [...YANTRA_UP, ...YANTRA_DOWN];

function yantraTrianglePoints(t: YantraTriangleSpec): string {
  const sign = t.dir === "up" ? -1 : 1;
  const apexY = YANTRA_CY + sign * t.apex * YANTRA_R;
  const baseY = YANTRA_CY - sign * t.base * YANTRA_R;
  const hw = t.halfWidth * YANTRA_R;
  return `${YANTRA_CX},${apexY} ${YANTRA_CX - hw},${baseY} ${YANTRA_CX + hw},${baseY}`;
}

// Accent "node" dots at the largest up/down triangles' 6 vertices — the
// same count/spirit as the hexagon motif this replaced, so the hero
// graphic still reads as a connected, colored network, not just static
// geometry.
const YANTRA_ACCENT_POINTS: { x: number; y: number; color: string }[] = [
  { x: YANTRA_CX, y: YANTRA_CY - YANTRA_UP[0]!.apex * YANTRA_R, color: "#a855f7" },
  {
    x: YANTRA_CX - YANTRA_UP[0]!.halfWidth * YANTRA_R,
    y: YANTRA_CY + YANTRA_UP[0]!.base * YANTRA_R,
    color: "#3b82f6",
  },
  {
    x: YANTRA_CX + YANTRA_UP[0]!.halfWidth * YANTRA_R,
    y: YANTRA_CY + YANTRA_UP[0]!.base * YANTRA_R,
    color: "#22c55e",
  },
  { x: YANTRA_CX, y: YANTRA_CY + YANTRA_DOWN[0]!.apex * YANTRA_R, color: "#fdba74" },
  {
    x: YANTRA_CX - YANTRA_DOWN[0]!.halfWidth * YANTRA_R,
    y: YANTRA_CY - YANTRA_DOWN[0]!.base * YANTRA_R,
    color: "#fca5a5",
  },
  {
    x: YANTRA_CX + YANTRA_DOWN[0]!.halfWidth * YANTRA_R,
    y: YANTRA_CY - YANTRA_DOWN[0]!.base * YANTRA_R,
    color: "#a855f7",
  },
];

const YANTRA_PETAL_COUNT = 12;
const YANTRA_PETAL_RING_R = YANTRA_R * 1.22;
const YANTRA_PETAL_LENGTH = YANTRA_R * 0.16;
const YANTRA_PETAL_WIDTH = YANTRA_R * 0.05;
// Classic 7-color rainbow (ROYGBIV), cycled across the 12 petals rather
// than every petal sharing the single rainbow-gradient stroke used
// everywhere else in the graphic — a deliberate one-off per explicit
// request, so the lotus ring reads as individually colored petals.
const YANTRA_PETAL_COLORS = [
  "#ef4444", // red
  "#f97316", // orange
  "#eab308", // yellow
  "#22c55e", // green
  "#3b82f6", // blue
  "#4338ca", // indigo
  "#8b5cf6", // violet
];

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
        <div className="relative mx-auto mb-8 max-w-[403px]" aria-hidden="true">
          <svg viewBox="0 0 600 260" className="relative h-auto w-full">
            <defs>
              <filter id="hero-graph-glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="14" />
              </filter>
            </defs>
            <circle
              cx={YANTRA_CX}
              cy={YANTRA_CY}
              r={YANTRA_R * 0.9}
              fill="url(#rainbow-accent-gradient)"
              opacity="0.22"
              filter="url(#hero-graph-glow)"
            />

            {/* Lotus petal ring, just outside the boundary circles. */}
            {Array.from({ length: YANTRA_PETAL_COUNT }, (_, i) => {
              const angle = (360 / YANTRA_PETAL_COUNT) * i;
              return (
                <ellipse
                  key={`petal-${i}`}
                  cx={YANTRA_CX}
                  cy={YANTRA_CY - YANTRA_PETAL_RING_R}
                  rx={YANTRA_PETAL_WIDTH}
                  ry={YANTRA_PETAL_LENGTH}
                  fill="none"
                  stroke={YANTRA_PETAL_COLORS[i % YANTRA_PETAL_COLORS.length]}
                  strokeWidth="1.3"
                  opacity="0.6"
                  transform={`rotate(${angle} ${YANTRA_CX} ${YANTRA_CY})`}
                />
              );
            })}

            {/* Two boundary circles enclosing the triangle lattice. */}
            <circle
              cx={YANTRA_CX}
              cy={YANTRA_CY}
              r={YANTRA_R * 1.08}
              fill="none"
              stroke="url(#rainbow-accent-gradient)"
              strokeWidth="1"
              opacity="0.3"
            />
            <circle
              cx={YANTRA_CX}
              cy={YANTRA_CY}
              r={YANTRA_R * 1.0}
              fill="none"
              stroke="url(#rainbow-accent-gradient)"
              strokeWidth="1"
              opacity="0.3"
            />

            {/* The 9 interlocking Shiva/Shakti triangles. */}
            {YANTRA_TRIANGLES.map((t, i) => (
              <polygon
                key={`yantra-triangle-${t.dir}-${i}`}
                points={yantraTrianglePoints(t)}
                fill="none"
                stroke="url(#rainbow-accent-gradient)"
                strokeWidth="1.3"
                opacity={0.35 + (1 - i / YANTRA_TRIANGLES.length) * 0.3}
              />
            ))}

            {/* Bindu — the central convergence point. Red, slowly
                flashing (hero-bindu-flash, globals.css) rather than a
                flat solid fill, per explicit request. */}
            <circle
              cx={YANTRA_CX}
              cy={YANTRA_CY}
              r="3.5"
              fill="#dc2626"
              style={{ animation: "hero-bindu-flash 3s ease-in-out infinite" }}
            />

            {YANTRA_ACCENT_POINTS.map((p) => (
              <circle key={`node-${p.x}-${p.y}`} cx={p.x} cy={p.y} r="6" fill={p.color} />
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
