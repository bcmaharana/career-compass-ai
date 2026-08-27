import {
  Bot,
  Briefcase,
  ClipboardList,
  Contact,
  FileSearch,
  FileText,
  Gauge,
  GraduationCap,
  LineChart,
  MessageCircleQuestion,
  Settings,
  SlidersHorizontal,
  Sparkles,
  UserCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Short page purpose line shown in the fixed Header (brief Part 1.3). */
  purpose: string;
  /** Exact-match only (mirrors NavLink's `end` prop) — otherwise prefix match. */
  end?: boolean;
  /** Nested pages that live under this item in the rail (a "+" toggle
   * reveals them — see DesktopShell.tsx) rather than sitting as their
   * own top-level entry. Only ever one level deep — this app has no
   * need for a deeper tree yet, so the type/rendering don't try to
   * support one. */
  children?: NavItem[];
}

export const NAV_ITEMS: NavItem[] = [
  {
    to: "/dashboard",
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
    icon: Bot,
    purpose: "Get personalized, AI-guided career coaching.",
  },
  {
    to: "/resumes",
    label: "Resume Intelligence",
    icon: FileText,
    purpose: "Upload resumes, review AI-extracted details, and manage your resume history.",
  },
  {
    to: "/opportunities",
    label: "Opportunity Intelligence",
    icon: Briefcase,
    purpose: "Discover matching job listings and see your career path forward.",
    children: [
      {
        to: "/jd-tailoring",
        label: "JD Tailoring",
        icon: FileSearch,
        purpose:
          "Chat with the AI about a specific job description and generate a tailored resume.",
      },
      {
        to: "/job-applications",
        label: "Job Applications",
        icon: ClipboardList,
        purpose: "Track applications through your pipeline, with interview rounds logged per application.",
      },
      {
        to: "/recruiter-contacts",
        label: "Recruiter Contacts",
        icon: Contact,
        purpose: "Your address book of recruiters and hiring contacts.",
      },
    ],
  },
  {
    to: "/learning",
    label: "Learning Intelligence",
    icon: GraduationCap,
    purpose: "Track your learning log and get AI-recommended resources for your skill gaps.",
    children: [
      {
        to: "/interview-prep",
        label: "Interview Prep",
        icon: MessageCircleQuestion,
        purpose: "Build study notes and practice interview questions, with AI-suggested answers.",
      },
    ],
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
/**
 * Profile, Platform Admin, and Account (delete) moved to the platform
 * Hub's own Settings (2026-08-26) — the Hub is now the canonical
 * identity, so editing profile fields, managing platform-admin access,
 * and deleting the account all happen there instead. Only the two
 * CCAI-specific settings remain here.
 */
export const SETTINGS_NAV_ITEMS: NavItem[] = [
  {
    to: "/settings/ai-model",
    label: "AI Model",
    icon: Bot,
    end: true,
    purpose: "Choose which AI model powers your Career Coach chat.",
  },
  {
    to: "/settings/job-search-preference",
    label: "Job Search Preference",
    icon: SlidersHorizontal,
    end: true,
    purpose: "Set the location and filters used when searching for job listings.",
  },
];

/** No item in SETTINGS_NAV_ITEMS needs special-access gating any more
 * (Platform Admin, the one that did, moved to the Hub) — kept as its
 * own export since AccountPanelContent.tsx and other callers still
 * reference it by this name. */
export const STANDARD_SETTINGS_NAV_ITEMS: NavItem[] = SETTINGS_NAV_ITEMS;

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

/** Header title/purpose only for the post-login `/welcome` page — kept
 * out of NAV_ITEMS the same way SETTINGS_LANDING_ITEM is kept out of
 * SETTINGS_NAV_ITEMS above, so it never renders as a Left Nav link. */
const WELCOME_ITEM: NavItem = {
  to: "/welcome",
  label: "Welcome",
  icon: Sparkles,
  end: true,
  purpose: "Pick up where you left off.",
};

export function isSettingsRoute(pathname: string): boolean {
  return pathname.startsWith("/settings");
}

/** Parents plus their children, flattened one level — everywhere that
 * needs to *match* a pathname against the nav tree (rather than render
 * it) doesn't care about the parent/child structure, just the full set
 * of real destinations. */
function flattenNavItems(items: NavItem[]): NavItem[] {
  return items.flatMap((item) => [item, ...(item.children ?? [])]);
}

function matchAgainst(items: NavItem[], pathname: string): NavItem | undefined {
  return [...flattenNavItems(items)]
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
  if (pathname === "/welcome") return WELCOME_ITEM;
  if (isSettingsRoute(pathname)) {
    return matchAgainst(SETTINGS_NAV_ITEMS, pathname) ?? SETTINGS_LANDING_ITEM;
  }
  return matchAgainst(NAV_ITEMS, pathname) ?? NAV_ITEMS[0]!;
}

export interface BreadcrumbSegment {
  label: string;
  /** Omitted on the last segment — the current page is never a link. */
  href?: string;
}

/**
 * Layer-2/layer-3 breadcrumb trail for the current authenticated route —
 * "Hub" itself is prepended separately by whatever renders this (a
 * constant, not route-dependent). "Career Compass AI" always links to
 * /dashboard, matching the app's own top-level home. A NAV_ITEMS child
 * (e.g. Interview Prep under Learning Intelligence) gets its parent as a
 * middle segment; a top-level item or the /welcome page gets a flat
 * 2-segment trail; /settings/* gets "Settings" as the middle segment,
 * mirroring matchNavItem's own branching rather than duplicating it.
 */
export function getBreadcrumbTrail(pathname: string): BreadcrumbSegment[] {
  const trail: BreadcrumbSegment[] = [{ label: "Career Compass AI", href: "/dashboard" }];

  if (pathname === "/welcome") {
    trail.push({ label: WELCOME_ITEM.label });
    return trail;
  }

  if (isSettingsRoute(pathname)) {
    const item = matchAgainst(SETTINGS_NAV_ITEMS, pathname);
    if (!item) {
      trail.push({ label: SETTINGS_LANDING_ITEM.label });
      return trail;
    }
    trail.push({ label: SETTINGS_LANDING_ITEM.label, href: "/settings" });
    trail.push({ label: item.label });
    return trail;
  }

  for (const parent of NAV_ITEMS) {
    const child = parent.children?.find((c) =>
      c.end ? pathname === c.to : pathname.startsWith(c.to),
    );
    if (child) {
      trail.push({ label: parent.label, href: parent.to });
      trail.push({ label: child.label });
      return trail;
    }
  }

  const item = matchAgainst(NAV_ITEMS, pathname) ?? NAV_ITEMS[0]!;
  trail.push({ label: item.label });
  return trail;
}
