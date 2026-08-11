import type { Config } from "tailwindcss";

// Career Compass AI design tokens.
// Palette is fixed by the product brief (deep blue / teal / light gray /
// white cards); the specific shades and the typography pairing below are
// this project's deliberate choices — see docs/architecture/frontend-architecture.md
// for the rationale (Sora for display type gives the "AI-enabled, modern"
// character the brief asks for without leaning on Inter-everywhere or the
// now-common Space-Grotesk-for-every-AI-product default).
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      // Tighter side padding on phone widths (1rem = 16px) than desktop
      // (1.5rem) — a global win for content width on small screens without
      // touching every page individually.
      padding: { DEFAULT: "1rem", md: "1.5rem" },
      screens: { "2xl": "1400px" },
    },
    extend: {
      fontFamily: {
        display: ["Sora", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["\"IBM Plex Mono\"", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        border: "hsl(var(--border))",
        ring: "hsl(var(--ring))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(16 24 40 / 0.05), 0 1px 3px 0 rgb(16 24 40 / 0.08)",
      },
    },
  },
  plugins: [],
} satisfies Config;
