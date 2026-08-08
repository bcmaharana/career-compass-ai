import { Bot, FileText, Gauge, LineChart, Settings, Sparkles, User, UserCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Short page purpose line shown in the fixed Header (brief Part 1.3). */
  purpose: string;
  /** Exact-match only (mirrors NavLink's `end` prop) — otherwise prefix match. */
  end?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  {
    to: "/",
    label: "Dashboard",
    icon: Gauge,
    end: true,
    purpose: "Your career intelligence at a glance.",
  },
  {
    to: "/profile",
    label: "Career Profile",
    icon: UserCircle,
    purpose: "Build and maintain the living career profile everything else draws from.",
  },
  {
    to: "/skills",
    label: "Skill Intelligence",
    icon: LineChart,
    purpose: "Track your skills and proficiency over time.",
  },
  {
    to: "/coach",
    label: "AI Career Coach",
    icon: Sparkles,
    purpose: "Get personalized, AI-guided career coaching.",
  },
  {
    to: "/resumes",
    label: "Resume Intelligence",
    icon: FileText,
    purpose: "Upload resumes, review AI-extracted details, and manage your resume history.",
  },
];

/**
 * Right Nav's middle section swaps to this list under /settings
 * (RightNav.tsx) — its own sub-navigation, the same way most apps
 * separate "the product" from "your account." Just Profile for now;
 * future settings categories (Security, Notifications, ...) are
 * additional entries here, not a new mechanism. Deliberately does NOT
 * include a "/settings" landing entry — /settings itself shows a plain
 * "pick a category" message (SettingsLandingPage) rather than
 * defaulting into Profile, so nothing here should render as if it were
 * already selected.
 */
export const SETTINGS_NAV_ITEMS: NavItem[] = [
  {
    to: "/settings/profile",
    label: "Profile",
    icon: User,
    end: true,
    purpose: "View and update your name and title.",
  },
  {
    to: "/settings/ai-model",
    label: "AI Model",
    icon: Bot,
    end: true,
    purpose: "Choose which AI model powers your Career Coach chat.",
  },
];

/** Header title/purpose only for the bare /settings landing page — kept
 * out of SETTINGS_NAV_ITEMS so it never renders as a clickable sub-nav
 * button in the Right Nav (there's nothing to navigate *to*, you're
 * already there). */
const SETTINGS_LANDING_ITEM: NavItem = {
  to: "/settings",
  label: "Settings",
  icon: Settings,
  end: true,
  purpose: "Choose a category from the panel on the right.",
};

export function isSettingsRoute(pathname: string): boolean {
  return pathname.startsWith("/settings");
}

function matchAgainst(items: NavItem[], pathname: string): NavItem | undefined {
  return [...items]
    .sort((a, b) => b.to.length - a.to.length)
    .find((item) => (item.end ? pathname === item.to : pathname.startsWith(item.to)));
}

/**
 * Which nav item a given pathname belongs to — the longest matching `to`
 * prefix wins (so e.g. a future `/profile/edit` still matches the Career
 * Profile item), falling back to the first main-app item, or to the
 * settings-landing item under /settings. Shared by AppShell (to detect a
 * genuine section change, which clears the chat thread) and AppHeader
 * (to show the right page name/purpose).
 */
export function matchNavItem(pathname: string): NavItem {
  if (isSettingsRoute(pathname)) {
    return matchAgainst(SETTINGS_NAV_ITEMS, pathname) ?? SETTINGS_LANDING_ITEM;
  }
  return matchAgainst(NAV_ITEMS, pathname) ?? NAV_ITEMS[0]!;
}
