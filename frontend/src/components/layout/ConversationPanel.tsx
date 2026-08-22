import {
  useClearChatMessages,
  useDeleteChatConversation,
  useDeleteChatMessage,
} from "@/api/queries/chat";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { renderMarkdownMessage } from "@/lib/markdown-message";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";
import type { ChatThreadMessage } from "@/stores/chat-store";
import { matchNavItem } from "@/lib/nav-items";
import { Bot, Eraser, Trash2, UserCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

const RAINBOW_GRADIENT =
  "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]";

interface ConversationPanelProps {
  /** "Conversation" on the footer bar (every page); CoachPage.tsx passes
   * nothing, same default — the AI Career Coach page has no need for a
   * different label. */
  title?: string;
}

/**
 * The one, single rendering of "the current AI conversation" — shared by
 * the footer bar (every page, via ChatThread.tsx re-exporting this) and
 * the dedicated AI Career Coach page (CoachPage.tsx), so the conversation
 * looks and behaves identically wherever it's shown (direct 2026-08-22
 * request: "the conversation design should be same every where"). Reads
 * chat-store.ts directly rather than taking messages as a prop — every
 * caller is looking at the exact same store, so there was never a real
 * reason for two separate implementations to exist in the first place.
 *
 * Deletion is per question+answer turn (direct request: "deletion is per
 * question answer") via the hover-revealed trash icon on each bubble —
 * Clear/Delete conversation in the header are the coarser, whole-
 * conversation actions, matching JD Tailoring's own three-tier
 * clear/delete/per-message trio exactly.
 */
export function ConversationPanel({ title = "Conversation" }: ConversationPanelProps) {
  const location = useLocation();
  const sectionKey = matchNavItem(location.pathname).to;

  const messages = useChatStore((state) => state.messages);
  const isSending = useChatStore((state) => state.isSending);
  const conversationId = useChatStore((state) => state.conversationId);
  const clearChatMessages = useChatStore((state) => state.clear);
  const resetChatConversation = useChatStore((state) => state.resetConversation);
  const removeChatMessages = useChatStore((state) => state.removeMessages);

  const clearMessages = useClearChatMessages();
  const deleteConversation = useDeleteChatConversation(sectionKey);
  const deleteMessage = useDeleteChatMessage(conversationId ?? "");
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [deleteConversationConfirmOpen, setDeleteConversationConfirmOpen] = useState(false);
  const [deleteMessageTargetId, setDeleteMessageTargetId] = useState<string | null>(null);

  const conversationScrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = conversationScrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, isSending]);

  if (messages.length === 0 && !isSending) {
    return null;
  }

  function handleConfirmClear() {
    if (!conversationId) return;
    clearMessages.mutate(conversationId, {
      onSuccess: () => {
        clearChatMessages();
        setClearConfirmOpen(false);
      },
    });
  }

  function handleConfirmDeleteConversation() {
    if (!conversationId) return;
    deleteConversation.mutate(conversationId, {
      onSuccess: () => {
        resetChatConversation();
        setDeleteConversationConfirmOpen(false);
      },
    });
  }

  function handleConfirmDeleteMessage() {
    if (!deleteMessageTargetId) return;
    deleteMessage.mutate(deleteMessageTargetId, {
      onSuccess: (data) => {
        removeChatMessages(data.deleted_message_ids);
        setDeleteMessageTargetId(null);
      },
    });
  }

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <CardTitle>{title}</CardTitle>
        <div className="flex items-center gap-1">
          <Button type="button" variant="ghost" size="sm" onClick={() => setClearConfirmOpen(true)}>
            <Eraser className="h-3.5 w-3.5" />
            Clear conversation
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-destructive hover:text-destructive"
            onClick={() => setDeleteConversationConfirmOpen(true)}
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete conversation
          </Button>
        </div>
      </CardHeader>
      <CardContent
        ref={conversationScrollRef}
        className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto scrollbar-hide"
      >
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            onDelete={() => setDeleteMessageTargetId(message.id)}
          />
        ))}
        {isSending && <TypingBubble />}
      </CardContent>

      <ConfirmDialog
        open={clearConfirmOpen}
        onCancel={() => setClearConfirmOpen(false)}
        onConfirm={handleConfirmClear}
        title="Clear this conversation?"
        description="Removes every message in this conversation. This can't be undone."
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
        isPending={clearMessages.isPending}
      />

      <ConfirmDialog
        open={deleteConversationConfirmOpen}
        onCancel={() => setDeleteConversationConfirmOpen(false)}
        onConfirm={handleConfirmDeleteConversation}
        title="Delete this conversation?"
        description="Removes the whole conversation. Your next message starts a brand-new one. This can't be undone."
        isPending={deleteConversation.isPending}
      />

      <ConfirmDialog
        open={deleteMessageTargetId !== null}
        onCancel={() => setDeleteMessageTargetId(null)}
        onConfirm={handleConfirmDeleteMessage}
        title="Delete this message?"
        description="Removes this message and its paired question/answer, if there is one. This can't be undone."
        isPending={deleteMessage.isPending}
      />
    </Card>
  );
}

function MessageBubble({
  message,
  onDelete,
}: {
  message: ChatThreadMessage;
  onDelete: () => void;
}) {
  const isUser = message.role === "user";
  return (
    <div className={cn("group flex items-start gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-muted text-muted-foreground" : cn(RAINBOW_GRADIENT, "text-primary"),
        )}
      >
        {isUser ? <UserCircle className="h-5 w-5" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className={cn("flex max-w-2xl flex-col gap-1", isUser && "items-end")}>
        <div className={cn("flex items-center gap-1.5", isUser && "flex-row-reverse")}>
          <span className="text-xs font-medium text-muted-foreground">
            {isUser ? "You" : "AI Career Coach"}
          </span>
          <button
            type="button"
            onClick={onDelete}
            aria-label="Delete this message"
            title="Delete this message"
            className="text-muted-foreground opacity-0 transition-opacity hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
        <div
          className={cn(
            "rounded-lg px-4 py-2.5 text-sm",
            isUser
              ? "whitespace-pre-wrap bg-primary text-primary-foreground"
              : "bg-muted text-foreground",
          )}
        >
          {isUser ? message.content : renderMarkdownMessage(message.content)}
        </div>
      </div>
    </div>
  );
}

/** Real LLM calls can take several seconds, so this is the only signal
 * the user gets that the AI Career Coach is actually working. */
function TypingBubble() {
  return (
    <div className="flex items-start gap-3" role="status" aria-label="AI Career Coach is thinking">
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-primary",
          RAINBOW_GRADIENT,
        )}
      >
        <Bot className="h-4 w-4" />
      </div>
      <div className="flex items-center gap-1 rounded-lg bg-muted px-4 py-3">
        {[0, 150, 300].map((delayMs) => (
          <span
            key={delayMs}
            className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/60"
            style={{ animationDelay: `${delayMs}ms` }}
          />
        ))}
      </div>
    </div>
  );
}
