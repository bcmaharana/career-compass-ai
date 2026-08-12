import { create } from "zustand";

/**
 * Footer AI Chat thread state (UI enhancement brief Part 1.2).
 *
 * Holds only the *currently visible* thread — the conversation itself is
 * persisted server-side on every message (see api/queries/chat.ts), but
 * this store's `messages` array is deliberately ephemeral: navigating to
 * a different Left Nav item clears it (see AppShell.tsx), which is what
 * makes the thread disappear from the center panel on nav while the
 * underlying conversation stays retrievable in the database.
 *
 * `conversationId` deliberately does NOT reset on `clear()` — a real bug,
 * not just a docstring mismatch: `clear()` used to wipe it too, so the
 * very next message after any navigation created a brand-new, empty
 * conversation server-side instead of continuing the existing one,
 * because ChatService only loads history for a conversation_id it's
 * actually given (see chat_service.py's `_resolve_conversation_id` —
 * `None` always creates fresh). The visible thread still starts empty on
 * a new page (matching the stated intent above), but the next message
 * sent from anywhere correctly continues the same conversation and
 * reaches the LLM with its full prior history, even though the bubbles
 * that produced that history aren't re-rendered on screen.
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
  addAssistantMessage: (conversationId: string, message: ChatThreadMessage) => void;
  setSending: (isSending: boolean) => void;
  clear: () => void;
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
  addAssistantMessage: (conversationId, message) =>
    set((state) => ({ conversationId, messages: [...state.messages, message] })),
  setSending: (isSending) => set({ isSending }),
  clear: () => set({ messages: [], isSending: false }),
  setConversationId: (conversationId) => set({ conversationId }),
}));
