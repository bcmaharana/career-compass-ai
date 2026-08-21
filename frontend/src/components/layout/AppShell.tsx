import { useChatMessages, useLatestConversation } from "@/api/queries/chat";
import { DesktopShell } from "@/components/layout/DesktopShell";
import { MobileShell } from "@/components/layout/MobileShell";
import { useAuthStore } from "@/stores/auth-store";
import { useChatStore } from "@/stores/chat-store";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

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
  const navigate = useNavigate();
  const location = useLocation();
  const clearSession = useAuthStore((state) => state.clearSession);
  const queryClient = useQueryClient();
  const isMobile = useIsMobileShell();

  const chatMessages = useChatStore((state) => state.messages);
  const setChatMessages = useChatStore((state) => state.setMessages);
  const chatConversationId = useChatStore((state) => state.conversationId);
  const setChatConversationId = useChatStore((state) => state.setConversationId);
  const mainRef = useRef<HTMLElement>(null);

  // Resumes the same AI chat conversation after a full page reload or a
  // fresh login — chat-store.ts's conversationId lives in memory only
  // (deliberately: it must not survive a *different* user logging in on
  // the same browser tab), which otherwise meant every reload/relogin
  // started a brand-new, historyless conversation even though the old
  // one and its messages were still sitting in the database.
  //
  // `hasAttemptedResumeRef` makes this a one-shot: a real bug caught live
  // (2026-08-21) had this effect keyed only on "is chatConversationId
  // currently null," which re-fired the moment "Delete conversation"
  // (CoachPage.tsx) reset it to null — `useLatestConversation()` has
  // `staleTime: Infinity` and was fetched once at mount, so its cached
  // data still held the just-deleted conversation's id, and this effect
  // immediately wrote that dead id straight back into the store. The
  // very next message then went out carrying a conversation_id the
  // backend had already removed, and silently 404'd
  // (CHAT_CONVERSATION_NOT_FOUND) instead of starting the fresh
  // conversation the user actually just asked for. A plain "only if
  // nothing's set yet" check can't distinguish "never resolved yet" from
  // "deliberately cleared" — a ref that never resets once the resume
  // attempt has happened (successful or not) can.
  const { data: latestConversation } = useLatestConversation();
  const hasAttemptedResumeRef = useRef(false);
  useEffect(() => {
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
  }, [latestConversation, chatConversationId, setChatConversationId]);

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

  function handleLogout() {
    clearSession();
    // The query cache is a module-level singleton, not scoped per
    // session — without clearing it, logging back in (even as a
    // different user) could briefly show whatever data the *previous*
    // session had cached before a background refetch replaced it.
    queryClient.clear();
    navigate("/", { replace: true });
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
    </div>
  );
}
