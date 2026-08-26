/**
 * Base URL of the sibling `enterprise/platform` repo's own frontend
 * (the "Hub") — used by the "Back to Hub" links in DesktopShell.tsx/
 * MobileNavMenu.tsx. Falls back to that repo's own fixed dev port
 * (:5174) rather than an empty string, so a fresh dev checkout without
 * VITE_PLATFORM_BASE_URL set in .env.local still gets a working link
 * instead of a broken one — matching this app's own fixed dev port
 * (:5173) fallback convention elsewhere. Production sets this via its
 * own build-time env (domain-agnostic principle — never hardcode a
 * real domain in source).
 */
export const PLATFORM_BASE_URL = import.meta.env.VITE_PLATFORM_BASE_URL ?? "http://localhost:5174";
