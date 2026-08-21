import { create } from "zustand";

/**
 * Footer AI Chat thread state (UI enhancement brief Part 1.2).
 *
 * The conversation is persisted server-side on every message (see
 * api/queries/chat.ts), and — as of 2026-08-21, direct request for
 * parity with JD Tailoring's own conversation persistence — the real
 * saved history is what's shown: `useChatMessages(conversationId)` (a
 * real GET, cached via TanStack Query) hydrates this store's `messages`
 * array via `setMessages` whenever the thread mounts with a known
 * conversation id, rather than the thread starting empty on every
 * navigation the way it used to. AppShell.tsx no longer clears the
 * visible thread on a Left Nav section change for this same reason —
 * the point now is exactly the opposite: the conversation should look
 * the same regardless of which page you navigated from.
 *
 * `conversationId` deliberately does NOT reset on `clear()` (used by the
 * "Clear conversation" action, which wipes messages but keeps the same
 * conversation row/id both server-side and here) — a real bug once
 * existed where `clear()` wiped it too, so the very next message
 * created a brand-new, empty conversation server-side instead of
 * continuing the existing one, because ChatService only loads history
 * for a conversation_id it's actually given (see chat_service.py's
 * `_resolve_conversation_id` — `None` always creates fresh). Deleting
 * the whole conversation (not just clearing it) is the one action that
 * DOES reset `conversationId` to `null` — see `resetConversation` below.
 *
 * The user's own message is added optimistically (client-generated id,
 * before the request resolves) so it appears the instant they hit send —
 * `isSending` then drives ChatThread's typing indicator until the
 * assistant's reply lands. Real LLM calls (Phase 4) can take several
 * seconds, especially against a local Ollama model, so a visible
 * in-progress state matters here in a way a placeholder echo never
 * needed.
 */

export interface ChatThreadMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ChatState {
  conversationId: string | null;
  messages: ChatThreadMessage[];
  isSending: boolean;
  addUserMessage: (message: ChatThreadMessage) => void;
  /** Reconciles the optimistic user bubble's client-generated id (from
   * addUserMessage, before the request resolved) with the real
   * server-assigned id, and appends the assistant's reply — done
   * together, atomically, so a delete on either bubble afterward always
   * targets a real, server-deletable id rather than the throwaway
   * client-side one, which the backend would silently no-op against. */
  confirmTurn: (
    conversationId: string,
    tempUserId: string,
    realUserId: string,
    assistantMessage: ChatThreadMessage,
  ) => void;
  setSending: (isSending: boolean) => void;
  /** Replaces the whole messages array — used to hydrate from a real
   * GET /chat/conversations/{id}/messages fetch, not an incremental
   * update. */
  setMessages: (messages: ChatThreadMessage[]) => void;
  /** Drops specific message ids from the visible thread — the
   * "Clear conversation"/delete-single-message actions confirm the
   * real ids removed server-side (a delete can remove a paired
   * question+answer together, not just the one clicked) and pass them
   * here rather than assuming which ids were affected. */
  removeMessages: (ids: string[]) => void;
  /** "Clear conversation": wipes the visible thread, same conversation
   * id continues (see the class docstring above for why `clear()`
   * itself must never touch conversationId). */
  clear: () => void;
  /** "Delete conversation": the whole conversation is gone server-side,
   * so the next message must start a genuinely new one — the one case
   * where conversationId itself resets to null too. */
  resetConversation: () => void;
  /** AppShell.tsx calls this once, on mount, with whatever
   * useLatestConversation() finds — resuming the same conversation after
   * a full page reload or a fresh login, the same in-memory-only gap
   * `conversationId` surviving navigation (above) doesn't cover on its
   * own. Only sets it if nothing's set yet (see AppShell.tsx's own
   * guard), so this can never clobber a conversation already in
   * progress in this tab. */
  setConversationId: (conversationId: string) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  conversationId: null,
  messages: [],
  isSending: false,
  addUserMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  confirmTurn: (conversationId, tempUserId, realUserId, assistantMessage) =>
    set((state) => ({
      conversationId,
      messages: [
        ...state.messages.map((m) => (m.id === tempUserId ? { ...m, id: realUserId } : m)),
        assistantMessage,
      ],
    })),
  setSending: (isSending) => set({ isSending }),
  setMessages: (messages) => set({ messages }),
  removeMessages: (ids) => {
    const idSet = new Set(ids);
    set((state) => ({ messages: state.messages.filter((m) => !idSet.has(m.id)) }));
  },
  clear: () => set({ messages: [], isSending: false }),
  resetConversation: () => set({ messages: [], isSending: false, conversationId: null }),
  setConversationId: (conversationId) => set({ conversationId }),
}));
