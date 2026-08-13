import { buttonVariants } from "@/components/ui/button-variants";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { Compass, LineChart, Sparkles, UserCircle, UserPlus, Users } from "lucide-react";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";
import { Navigate, Link } from "react-router-dom";

// Background wave layer behind the hero graph (see LandingPage below) —
// a two-phase flow. Phase 1 ("flock", plays once on mount): every dot
// starts within a V/chevron formation just left of the main graph — a
// single "leader" dot at the apex (FLOCK_APEX_X/Y), with rows of 2, 3,
// 4... dots fanning out behind it (FLOCK_ROW_COUNTS), the classic geese-
// in-flight shape, not a circular cloud (a "sunflower"/golden-angle
// spiral cluster was tried first and, even non-touching, still read as
// one round blob rather than a flock; a plain rectangular grid before
// that read as a solid block for the same reason — see the flockX/
// flockY comment below for the actual row-fan math). Two *independent*
// animations run on every flock dot at once, on two
// different CSS properties so they don't fight over one another:
// `transform` carries `hero-wave-flock-orbit` — one shared, `linear`
// elliptical lap around the main graph (24 closely-spaced keyframe
// points, not few-and-eased — an 8-point `ease-in-out` version was
// tried first and, verified live, visibly paused at each of the 8
// waypoints instead of gliding continuously; `linear` timing across
// enough points is what actually reads as one smooth sweep), identical
// for every dot (so the whole cluster glides together, in sync, like a
// flock's collective path) — and the separate `translate` property (a
// distinct CSS property since Transforms Level 2, composes with
// `transform` rather than overriding it) carries a small, quick,
// per-dot `hero-wave-fly-N` jitter, so each individual dot still darts
// around on its own erratic little path the way a fly does, layered on
// top of the group's smooth bird-like glide. Phase 2 ("scattered", after
// FLOCK_DURATION_S): each dot's cx/cy switches to its own scattered rest
// position (a jittered grid spanning the full canvas) and its animation
// switches to its individual big, sweeping `hero-wave-flight-N` path —
// see the per-dot comment below for why those are shaped the way they
// are. The cx/cy change is a plain CSS transition (not a keyframe), so
// the swap from "circling together" to "peeling off individually" reads
// as the flock dispersing, not a jump cut. Color (`hero-wave-hue`)
// cycles the same way in both phases.
const HUB_Y = 140;
// V-formation: row 0 is the single leader at the apex; rows 1-8 each add
// one more dot than the last (2, 3, 4, ... 9), fanning out behind it;
// the last entry is a shorter final row so the counts sum to exactly 48
// (1+2+...+9 = 45, +3 = 48) without needing a 10th full row that would
// push the formation's tail too far back.
const FLOCK_ROW_COUNTS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 3];
const FLOCK_ROW_SPACING = 20; // depth between rows — more than a dot's max diameter (14) alone, plus extra margin since a row's *outer* dots can still be diagonally close to the next row's, not just directly behind
const FLOCK_HALF_ANGLE_DEG = 26; // how wide the V opens, for rows with enough dots that this is the binding constraint (see FLOCK_ROW_DOT_SPACING)
const FLOCK_ROW_DOT_SPACING = 24; // minimum lateral spacing between dots *within* a row — the early rows (2-3 dots) are so close to the apex that the V's own angle alone would space them closer than this and touch; this floor wins for most rows
const FLOCK_APEX_X = 170; // the leader's position — left of the graph, clear of the main graph's left node (edge at x=181)
const FLOCK_APEX_Y = HUB_Y;
const FLOCK_DURATION_S = 4;
const FLOCK_FLY_VARIANT_COUNT = 4;
const SCATTER_TRANSITION_S = 1.4;

function flockRowInfo(seed: number): { row: number; indexInRow: number; rowCount: number } {
  let remaining = seed;
  for (let row = 0; row < FLOCK_ROW_COUNTS.length; row++) {
    // Safe: the loop bound (FLOCK_ROW_COUNTS.length) guarantees this index is in range.
    const rowCount = FLOCK_ROW_COUNTS[row]!;
    if (remaining < rowCount) return { row, indexInRow: remaining, rowCount };
    remaining -= rowCount;
  }
  throw new Error(`seed ${seed} exceeds FLOCK_ROW_COUNTS total`);
}

// Phase 2: dots scatter across the *entire* canvas (a jittered grid, not
// rows confined to one horizontal band) and each glides along one of six
// big, sweeping `hero-wave-flight-N` keyframes (globals.css) — long
// diagonal-ish arcs that carry a dot most of the way from one side of
// the graphic toward the other before looping, closer to a bird's glide
// than a small in-place wobble. `ease-in-out` (not `linear`) so each
// flight naturally accelerates/decelerates like a real glide rather than
// moving at a robotic constant rate — every dot still shares the same
// duration, so their overall pace reads as consistent even though
// instantaneous speed within a glide isn't literally constant. Vertical
// travel is deliberately much smaller than horizontal (~40 vs ~180 user
// units): the hero graphic sits close under the fixed header and just
// above the page heading, so large vertical excursions would visibly
// fly into that surrounding text — horizontal has open page whitespace
// on both sides, so dots can roam there freely (the wave svg is also
// `overflow-visible`, so a flight path is never hard-clipped). Color
// comes from a *shared* hue-rotate cycle (`hero-wave-hue`) whose per-dot
// delay is a smooth function of each dot's starting x position — every
// dot uses the same duration there too, so at any instant the hue varies
// smoothly left to right (a rainbow gradient), and since every dot's
// clock advances together, that gradient visibly travels across the
// graphic over time — a genuine moving spectrum-of-light band, layered
// independently on top of the flight motion. Deliberately CSS
// animations, not SVG SMIL: a dynamically React-inserted
// <animateTransform> was tried first and found (verified live) to not
// reliably auto-start in Chromium, needing a manual JS kick — CSS
// keyframes have no such quirk. Per-dot variety (starting position,
// flight variant, delay) comes from a small deterministic hash of each
// dot's index, not Math.random(), so the layout is stable across
// re-renders.
const WAVE_COLORS = ["#a855f7", "#3b82f6", "#22c55e", "#fdba74", "#fca5a5"];
const WAVE_GRID_COLS = 6;
const WAVE_GRID_ROWS = 8;
const CANVAS_W = 600;
const CANVAS_H = 260;
const WAVE_FLIGHT_VARIANT_COUNT = 6;
const WAVE_FLIGHT_DURATION_S = 9;
const HUE_CYCLE_DURATION_S = 7;
const WAVE_DOTS = Array.from({ length: WAVE_GRID_ROWS }, (_, rowIndex) =>
  Array.from({ length: WAVE_GRID_COLS }, (_, colIndex) => {
    const seed = rowIndex * WAVE_GRID_COLS + colIndex;
    const baseX = (colIndex + 0.5) * (CANVAS_W / WAVE_GRID_COLS);
    const baseY = (rowIndex + 0.5) * (CANVAS_H / WAVE_GRID_ROWS);
    const x = baseX + (((seed * 37) % 41) - 20);
    const y = baseY + (((seed * 53) % 21) - 10);
    const hueDelay = -((x / CANVAS_W) * HUE_CYCLE_DURATION_S);
    const flightVariant = (seed % WAVE_FLIGHT_VARIANT_COUNT) + 1;
    const flightDelay = -(((seed * 13) % (WAVE_FLIGHT_DURATION_S * 10)) / 10);
    // V-formation position: `flockRowInfo` turns this dot's linear seed
    // into (which row behind the leader, position within that row).
    // depth = how far behind the apex the row sits; halfWidth = how far
    // the V has widened by that depth (row 0, the leader, has width 0).
    // halfWidth is the *larger* of the angle-based width and a floor
    // that guarantees FLOCK_ROW_DOT_SPACING between adjacent dots in
    // this row — the angle alone put row 1's 2 dots close enough to
    // overlap (verified live), since depth is still small that close to
    // the apex; the floor dominates for every row except the last.
    const { row: flockRow, indexInRow, rowCount } = flockRowInfo(seed);
    const depth = flockRow * FLOCK_ROW_SPACING;
    const angleHalfWidth = depth * Math.tan((FLOCK_HALF_ANGLE_DEG * Math.PI) / 180);
    const minHalfWidth = ((rowCount - 1) * FLOCK_ROW_DOT_SPACING) / 2;
    const halfWidth = Math.max(angleHalfWidth, minHalfWidth);
    const lateral = rowCount > 1 ? (indexInRow / (rowCount - 1) - 0.5) * 2 * halfWidth : 0;
    const flyVariant = (seed % FLOCK_FLY_VARIANT_COUNT) + 1;
    const flyDuration = 0.5 + (seed % 5) * 0.08;
    const flyDelay = -((seed % 9) * 0.1);
    return {
      key: `${rowIndex}-${colIndex}`,
      x,
      y,
      flockX: FLOCK_APEX_X - depth,
      flockY: FLOCK_APEX_Y + lateral,
      r: 5 + (seed % 3),
      color: WAVE_COLORS[seed % WAVE_COLORS.length],
      style: {
        animation: `hero-wave-flight-${flightVariant} ${WAVE_FLIGHT_DURATION_S}s ease-in-out ${flightDelay}s infinite, hero-wave-hue ${HUE_CYCLE_DURATION_S}s linear ${hueDelay}s infinite`,
        transition: `cx ${SCATTER_TRANSITION_S}s ease-out, cy ${SCATTER_TRANSITION_S}s ease-out`,
      } as CSSProperties,
      flockStyle: {
        animation: `hero-wave-flock-orbit ${FLOCK_DURATION_S}s linear 1, hero-wave-fly-${flyVariant} ${flyDuration}s ease-in-out ${flyDelay}s infinite, hero-wave-hue ${HUE_CYCLE_DURATION_S}s linear ${hueDelay}s infinite`,
      } as CSSProperties,
    };
  }),
).flat();

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
  const [wavePhase, setWavePhase] = useState<"flock" | "scattered">("flock");

  useEffect(() => {
    const timer = setTimeout(() => setWavePhase("scattered"), FLOCK_DURATION_S * 1000);
    return () => clearTimeout(timer);
  }, []);

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
          {/* Animated background wave, two phases (see the WAVE_DOTS
              comment above): dots flock together in a circle around the
              graph on load, then disperse into independent, wandering
              flight — shimmering through the color spectrum throughout. */}
          <svg viewBox="0 0 600 260" className="absolute inset-0 h-full w-full overflow-visible">
            <g opacity="0.6">
              {WAVE_DOTS.map((dot) =>
                wavePhase === "flock" ? (
                  <circle key={dot.key} cx={dot.flockX} cy={dot.flockY} r={dot.r} fill={dot.color} style={dot.flockStyle} />
                ) : (
                  <circle key={dot.key} cx={dot.x} cy={dot.y} r={dot.r} fill={dot.color} style={dot.style} />
                ),
              )}
            </g>
          </svg>

          <svg viewBox="0 0 600 260" className="relative h-auto w-full">
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
