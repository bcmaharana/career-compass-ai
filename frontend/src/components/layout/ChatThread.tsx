import { ConversationPanel } from "@/components/layout/ConversationPanel";

/**
 * Renders the current AI Chat conversation below whatever page content is
 * already in the center panel (brief Part 1.2) — never in place of it.
 * A thin wrapper around ConversationPanel (2026-08-22: extracted so the
 * exact same conversation UI — including Clear/Delete conversation and
 * per-message delete — is shared with CoachPage.tsx rather than two
 * diverging implementations existing side by side) — kept as its own
 * named component/file since "ChatThread" is the name referenced
 * throughout this app's own documentation and comments.
 */
export function ChatThread() {
  return <ConversationPanel />;
}
