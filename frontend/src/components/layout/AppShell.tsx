import { useChatMessages, useLatestConversation } from "@/api/queries/chat";
import { DesktopShell } from "@/components/layout/DesktopShell";
import { MobileShell } from "@/components/layout/MobileShell";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { matchNavItem } from "@/lib/nav-items";
import { PLATFORM_BASE_URL } from "@/lib/platform";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

/** Matches Tailwind's `md` breakpoint (768px) — the mobile-shell
 * threshold. Mirrors DesktopShell.tsx's own NARROW_QUERY/getIsNarrow
 * pattern (hand-rolled `matchMedia`, since this also needs to gate which
 * whole component tree renders, not just a CSS class), just one
 * breakpoint lower and for a structural swap rather than a rail's width.
 * A pure-CSS hide/show of both DesktopShell and MobileShell was
 * considered and rejected: they have genuinely different `<main>` inset
 * math (rail widths vs. no rail + tab-bar height), and mounting both at
 * once would double up on the data-fetching hooks the account panel
 * calls (useCareerProfile, etc.) for no benefit.
 */
const MOBILE_QUERY = "(max-width: 767px)";

function getIsMobile(): boolean {
  return typeof window !== "undefined" && window.matchMedia(MOBILE_QUERY).matches;
}

function useIsMobileShell(): boolean {
  const [isMobile, setIsMobile] = useState(getIsMobile);

  useEffect(() => {
    const mediaQueryList = window.matchMedia(MOBILE_QUERY);
    function handleChange(event: MediaQueryListEvent) {
      setIsMobile(event.matches);
    }
    mediaQueryList.addEventListener("change", handleChange);
    return () => mediaQueryList.removeEventListener("change", handleChange);
  }, []);

  return isMobile;
}

/**
 * Application shell root. Owns the state/effects that don't depend on
 * which layout renders — the scrollable center panel's ref (shared since
 * only one of DesktopShell/MobileShell's own `<main>` is ever mounted at
 * a time), resuming the AI chat conversation on mount, clearing the chat
 * thread on a genuine nav-section change, resetting scroll on route
 * change, auto-scrolling to a new message, and logout — then branches to
 * DesktopShell (rails + docked footer chat, `md` and up) or MobileShell
 * (bottom tab bar + slide-in sheets, below `md`) based on viewport width.
 * See those two files for the actual fixed regions each renders.
 */
export function AppShell() {
  const location = useLocation();
  const clearSession = useAuthStore((state) => state.clearSession);
  const queryClient = useQueryClient();
  const isMobile = useIsMobileShell();

  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);

  const chatMessages = useChatStore((state) => state.messages);
  const setChatMessages = useChatStore((state) => state.setMessages);
  const chatConversationId = useChatStore((state) => state.conversationId);
  const chatSectionKey = useChatStore((state) => state.sectionKey);
  const setChatConversationId = useChatStore((state) => state.setConversationId);
  const resetChatForSection = useChatStore((state) => state.resetForSection);
  const mainRef = useRef<HTMLElement>(null);

  // Which top-level section the current route belongs to (matchNavItem's
  // `.to` — the same concept nav-items.ts already exposes for the Left
  // Nav/Header) — the chat conversation is scoped to this, not to the
  // whole app (2026-08-22: a real production bug report, "In each page
  // I see the same AI conversation history," meant every section was
  // silently sharing one global conversation).
  const currentSectionKey = matchNavItem(location.pathname).to;

  // One-shot-per-section-visit guard for the resume effect below —
  // declared here (rather than next to that effect) so the reset effect
  // immediately following can clear it too. See that resume effect's own
  // comment for why this can't just be "resume once ever."
  const hasAttemptedResumeRef = useRef(false);

  // The instant the active section changes, wipe the store and start a
  // fresh per-section resume — before that new section's own
  // latest-conversation fetch even resolves, so section B never shows
  // section A's messages, not even for one render. This also covers the
  // very first render (chatSectionKey starts out `null`), so no separate
  // mount-only reset is needed. Also clears `hasAttemptedResumeRef`
  // (below) — a real bug caught live (2026-08-22): that ref used to be
  // keyed by section NAME and never cleared once a section had been
  // visited once, so navigating away and back to the SAME section (e.g.
  // Dashboard -> Skills -> Dashboard) hit the "already attempted, don't
  // resume again" early-return from the section's very first visit and
  // silently left conversationId at the `null` this same effect had just
  // reset it to — the conversation looked wiped on every revisit even
  // though it was still sitting in the database. Resetting the ref here,
  // on every genuine section change (including a revisit), fixes that:
  // each fresh arrival into a section gets its own resume attempt.
  useEffect(() => {
    if (chatSectionKey !== currentSectionKey) {
      resetChatForSection(currentSectionKey);
      hasAttemptedResumeRef.current = false;
    }
  }, [currentSectionKey, chatSectionKey, resetChatForSection]);

  // Resumes THAT SECTION's own conversation after a fresh page load, a
  // logout/login cycle, or switching into the section (including
  // re-entering one already visited this session) — chat-store.ts's
  // conversationId lives in memory only (deliberately: it must not
  // survive a *different* user logging in on the same browser tab, or
  // leak from one section into another), which otherwise meant every
  // reload/relogin/section-switch started a brand-new, historyless
  // conversation even though the old one and its messages were still
  // sitting in the database.
  //
  // `hasAttemptedResumeRef` makes this a one-shot PER SECTION VISIT —
  // cleared by the reset effect above every time the section actually
  // changes (see its comment for the real bug this exact shape fixes),
  // but otherwise sticky for the duration of one stay in a section: a
  // real bug caught live (2026-08-21) had an earlier version of this
  // effect with no such guard at all, which re-fired the moment "Delete
  // conversation" reset conversationId to null — useLatestConversation()
  // has `staleTime: Infinity` and is fetched once per section, so its
  // cached data still held the just-deleted conversation's id, and the
  // effect immediately wrote that dead id straight back into the store.
  // A plain "only if nothing's set yet" check can't distinguish "never
  // resolved yet" from "deliberately cleared" — a ref that only resets on
  // an actual section change can.
  const { data: latestConversation } = useLatestConversation(currentSectionKey);
  useEffect(() => {
    if (chatSectionKey !== currentSectionKey) return; // reset effect above hasn't landed yet
    if (hasAttemptedResumeRef.current) return;
    if (chatConversationId) {
      hasAttemptedResumeRef.current = true;
      return;
    }
    if (latestConversation === undefined) return; // still loading — wait for a real answer
    hasAttemptedResumeRef.current = true;
    if (latestConversation.conversation_id) {
      setChatConversationId(latestConversation.conversation_id);
    }
  }, [
    currentSectionKey,
    chatSectionKey,
    latestConversation,
    chatConversationId,
    setChatConversationId,
  ]);

  // Hydrates the visible thread with the real saved history the moment
  // a conversation id is known (2026-08-21, direct request for parity
  // with JD Tailoring's own persistence) — this used to instead clear
  // the thread on every Left Nav / tab bar section change, making the
  // conversation look wiped even though it was still sitting in the
  // database; now navigating around the app keeps showing the same
  // conversation, matching JD Tailoring's own session view. Only
  // populates the store when it's still empty (a mount-time or
  // conversation-just-resolved fetch) — never overwrites messages
  // already accumulating from an in-progress send in this tab, and
  // never fights the optimistic bubble a fresh `sendTurn` call just
  // added while its own request is still in flight.
  const { data: fetchedMessages } = useChatMessages(chatConversationId);
  useEffect(() => {
    if (!fetchedMessages || chatMessages.length > 0) return;
    setChatMessages(
      fetchedMessages.map((m) => ({ id: m.id, role: m.role as "user" | "assistant", content: m.content })),
    );
  }, [fetchedMessages, chatMessages.length, setChatMessages]);

  // Resets the center panel's own scroll position on every navigation.
  // `<main>` (in whichever of DesktopShell/MobileShell is mounted) is a
  // single persistent scroll container reused across every page via
  // `<Outlet/>` (the SPA never reloads/scrolls the actual window) — React
  // Router has no built-in scroll-restoration for a custom scroll
  // container like this, so without this effect, whatever scrollTop a
  // previous page was left at silently carries over onto the next page's
  // content. Keyed on `location.key` (a value React Router mints fresh
  // for every navigation entry), not `location.pathname` — the Career
  // Profile page's Master/Target-Role-Profile switcher
  // (TargetRolesWidget.tsx) navigates between `/profile` and
  // `/profile?role=<id>`, which only changes the query string, not the
  // pathname, so keying on pathname alone silently missed exactly this
  // case: switching roles kept whatever scroll position the previous
  // role's card list was left at instead of starting from the top.
  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0 });
  }, [location.key]);

  // Auto-scrolls the center panel down to reveal a newly appended
  // exchange, the same "new messages push the view down" behavior as
  // this chat interface itself — underlying page content just scrolls
  // out of view above, it's never removed.
  useEffect(() => {
    if (chatMessages.length === 0) return;
    mainRef.current?.scrollTo({ top: mainRef.current.scrollHeight, behavior: "smooth" });
  }, [chatMessages.length]);

  // Every "Sign out" trigger in the app shell (RightNav, AppFooter's
  // icon column, ProfileIconMenu, AccountPanelContent — see those files'
  // own onLogout threading) calls this same handler, so gating it behind
  // a confirmation here covers every one of them without touching any
  // of those call sites individually. The actual sign-out only runs once
  // performLogout() below is confirmed.
  function handleLogout() {
    setLogoutConfirmOpen(true);
  }

  function performLogout() {
    setLogoutConfirmOpen(false);
    clearSession();
    // The query cache is a module-level singleton, not scoped per
    // session — without clearing it, logging back in (even as a
    // different user) could briefly show whatever data the *previous*
    // session had cached before a background refetch replaced it.
    queryClient.clear();
    // A real cross-origin navigation (not react-router's navigate()) to
    // the Hub's own /logout — this app's sign-out can only clear ITS OWN
    // session; the Hub's session lives in a completely separate origin's
    // localStorage, unreachable from here any other way. Without this,
    // signing out of CCAI left the Hub's own session fully live — a real
    // reported gap: visiting the Hub afterward still showed signed in,
    // and clicking back into CCAI silently re-authenticated via a fresh
    // handoff with no re-login at all.
    window.location.href = `${PLATFORM_BASE_URL}/logout`;
  }

  return (
    <div className="fixed inset-0 overflow-hidden bg-background">
      {/* Hidden defs only — provides #rainbow-accent-gradient for icon
          strokes throughout both DesktopShell and MobileShell (the logo
          icon, active mobile tab icons, the sign-out icon, ...). Not
          rendered visually itself. */}
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

      {isMobile ? (
        <MobileShell mainRef={mainRef} onLogout={handleLogout} />
      ) : (
        <DesktopShell mainRef={mainRef} onLogout={handleLogout} />
      )}

      <ConfirmDialog
        open={logoutConfirmOpen}
        onCancel={() => setLogoutConfirmOpen(false)}
        onConfirm={performLogout}
        title="Sign out?"
        description="You'll be signed out of Career Compass AI and the Hub — every product you're signed into."
        confirmLabel="Sign out"
        confirmPendingLabel="Signing out..."
      />
    </div>
  );
}
