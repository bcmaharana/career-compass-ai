import { cva } from "class-variance-authority";

// The ONE place the rainbow gradient's literal Tailwind class lives for
// every INTERACTIVE element in the center pane (buttons, and anything
// styled to look/behave like one, e.g. Dialog's close button) — import
// this rather than re-typing the literal string in another file. That
// duplication is exactly what caused a real, live inconsistency: a
// UX rule change (rainbow-on-hover instead of rainbow-by-default) only
// reached the files that went through `buttonVariants` below, while a
// hand-copied duplicate elsewhere silently kept the old look.
//
// A plain exported string constant like this DOES work with Tailwind's
// JIT content scanner across file boundaries — it scans every project
// source file's raw text for class-shaped substrings, not just the
// file where a component happens to render, and doesn't care whether a
// literal string is inlined directly in JSX or sitting in an imported
// constant. What genuinely breaks the scanner is DYNAMIC construction —
// e.g. a template literal like `bg-[${someColor}]` — since there's no
// literal substring for it to find. This is a static string, not that.
export const RAINBOW_GRADIENT_BG =
  "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]";

// Deliberately its OWN separate literal, NOT built by gluing "hover:"
// onto RAINBOW_GRADIENT_BG via template-literal interpolation below —
// that was tried and is exactly the trap this comment is warning about.
// Tailwind's scanner needs "hover:bg-[...]" to appear as ONE complete,
// contiguous text token somewhere in the source to generate its CSS
// rule; splitting it into "hover:" + an interpolated `${...}` leaves
// two broken, unmatched fragments in the scanned text instead, and the
// hover effect silently never renders anywhere that reuses it — caught
// before it shipped, not after.
export const RAINBOW_GRADIENT_HOVER_BG =
  "hover:bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]";

// No background at rest, rainbow gradient only on hover — the exact
// pattern Career Profile's "+Add"/"Edit"/"Clear" buttons (variant=
// "ghost") already had, now the shared style for every non-destructive
// variant so it's genuinely one consistent rule across the whole center
// pane, defined once here, rather than something only some pages
// happened to already do. A first attempt at this gave primary/accent/
// outline a SOLID --accent background at rest instead — visually
// different from ghost's transparent rest state, which was a
// misreading of "normal" as "a solid brand color" rather than "no
// special background at all." Corrected after live comparison against
// the Career Profile buttons specifically.
const _INTERACTIVE_VARIANT = `${RAINBOW_GRADIENT_HOVER_BG} hover:text-primary`;

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium " +
    "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
    "focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: _INTERACTIVE_VARIANT,
        accent: _INTERACTIVE_VARIANT,
        outline: _INTERACTIVE_VARIANT,
        ghost: _INTERACTIVE_VARIANT,
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
      },
      size: {
        sm: "h-8 px-3",
        md: "h-10 px-4",
        lg: "h-12 px-6 text-base",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);
