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
 */

export interface ChatThreadMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ChatState {
  conversationId: string | null;
  messages: ChatThreadMessage[];
  appendTurn: (turn: {
    conversationId: string;
    userMessage: ChatThreadMessage;
    assistantMessage: ChatThreadMessage;
  }) => void;
  clear: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  conversationId: null,
  messages: [],
  appendTurn: ({ conversationId, userMessage, assistantMessage }) =>
    set((state) => ({
      conversationId,
      messages: [...state.messages, userMessage, assistantMessage],
    })),
  clear: () => set({ conversationId: null, messages: [] }),
}));
