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
  clear: () => set({ conversationId: null, messages: [], isSending: false }),
}));
