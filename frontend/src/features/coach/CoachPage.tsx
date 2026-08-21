import { useCareerProfile, useTargetRoles } from "@/api/queries/career-profile";
import {
  useClearChatMessages,
  useDeleteChatConversation,
  useDeleteChatMessage,
} from "@/api/queries/chat";
import { useGapAnalysis } from "@/api/queries/skill-intelligence";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { RichTextDisplay } from "@/components/ui/rich-text-editor";
import { buildSuggestedPrompts } from "@/features/coach/suggested-prompts";
import { getErrorMessage } from "@/lib/errors";
import { renderMarkdownMessage } from "@/lib/markdown-message";
import { cn } from "@/lib/utils";
import { useChatComposer } from "@/hooks/useChatComposer";
import { useChatStore } from "@/stores/chat-store";
import type { ChatThreadMessage } from "@/stores/chat-store";
import { resolveValidTargetRoleId, useTargetRoleScopeStore } from "@/stores/target-role-scope-store";
import { Bot, ChevronDown, ChevronRight, Eraser, Trash2, UserCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

const RAINBOW_GRADIENT =
  "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]";

/** Same click-anywhere-on-header/chevron accordion shell as
 * DashboardPage.tsx's DashboardCardShell — unlike Dashboard's own
 * single-open-at-a-time accordion, these two cards start independently
 * expanded (both open together — see `profileOpen`/`promptsOpen` below)
 * and only auto-collapse once a real conversation starts, so a plain
 * shared "which one card is open" enum doesn't fit here. Unlike
 * DashboardCardShell's optional `description` (hidden while collapsed),
 * `headerExtra` here always renders regardless of open state — the
 * "Showing: <role>" line is load-bearing context, not decorative, so
 * it stays visible even collapsed. */
function CollapsibleCard({
  title,
  headerExtra,
  isOpen,
  onToggle,
  children,
}: {
  title: string;
  headerExtra?: ReactNode;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader
        role="button"
        tabIndex={0}
        aria-expanded={isOpen}
        onClick={onToggle}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onToggle();
          }
        }}
        className="cursor-pointer select-none"
      >
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <CardTitle>{title}</CardTitle>
            {headerExtra}
          </div>
          {isOpen ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
        </div>
      </CardHeader>
      {isOpen && children}
    </Card>
  );
}

/**
 * The dedicated AI Career Coach page (`/coach`) — a full-page view onto
 * the same conversation the footer's persistent chat bar
 * (AppFooter.tsx/ChatThread.tsx) already sends into, via the shared
 * chat-store and useChatComposer. Nothing here talks to a different
 * conversation or a different endpoint; this page adds three things the
 * compact footer thread doesn't have room for:
 *
 *  1. A profile snapshot, so the person can see at a glance what the
 *     coach conversation can draw on.
 *  2. Suggested conversation starters built from that same profile data
 *     (suggested-prompts.ts) — clicking one sends it immediately via
 *     sendTurn, exactly as if it had been typed into the footer.
 *  3. A larger, labeled message thread (avatar + "You"/"AI Career
 *     Coach") instead of the footer thread's compact bubbles.
 *
 * AppShell.tsx suppresses the generic <ChatThread /> while on this
 * route specifically so the same messages array isn't rendered twice.
 *
 * Grounded in whichever role is currently active app-wide (see
 * target-role-scope-store.ts), set by picking a role on Career Profile
 * or any of the other role-aware pages — this page has no scope
 * selector of its own, it just reads whatever's already active: the
 * "profile at a glance" card shows that Target Role Profile (falling
 * back to Master when no role is active, or a stale/deleted one is
 * stored), and its own gap count and suggested prompt are prioritized
 * first among the personalized starters below.
 */
export function CoachPage() {
  const activeTargetRoleId = useTargetRoleScopeStore((s) => s.activeTargetRoleId);
  const { data: targetRoles } = useTargetRoles();
  const scopeRoleId = resolveValidTargetRoleId(activeTargetRoleId, targetRoles);
  const activeRole = scopeRoleId ? targetRoles?.find((r) => r.id === scopeRoleId) : null;

  const { data: profile } = useCareerProfile(scopeRoleId);
  const { data: gapAnalysis } = useGapAnalysis();

  const messages = useChatStore((state) => state.messages);
  const isSending = useChatStore((state) => state.isSending);
  const conversationId = useChatStore((state) => state.conversationId);
  const clearChatMessages = useChatStore((state) => state.clear);
  const resetChatConversation = useChatStore((state) => state.resetConversation);
  const removeChatMessages = useChatStore((state) => state.removeMessages);
  const { sendTurn, isError, error } = useChatComposer();

  // Conversation-management actions (2026-08-21, direct request: "the
  // delete conversation feature should be consistent everywhere" and
  // "keeping the conversation should be same as JD Tailoring") — mirror
  // JD Tailoring's own Clear conversation / delete conversation /
  // delete-single-message trio exactly, just against this page's single
  // ongoing conversation instead of a picked session.
  const clearMessages = useClearChatMessages();
  const deleteConversation = useDeleteChatConversation();
  const deleteMessage = useDeleteChatMessage(conversationId ?? "");
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [deleteConversationConfirmOpen, setDeleteConversationConfirmOpen] = useState(false);
  const [deleteMessageTargetId, setDeleteMessageTargetId] = useState<string | null>(null);

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

  // The active role's own prompt (if any) is guaranteed to appear first
  // among the role-based suggestions below — buildSuggestedPrompts walks
  // this list in order and stops after the first two role hits.
  const prioritizedTargetRoles = useMemo(() => {
    if (!targetRoles || !scopeRoleId) return targetRoles;
    const active = targetRoles.find((r) => r.id === scopeRoleId);
    if (!active) return targetRoles;
    return [active, ...targetRoles.filter((r) => r.id !== scopeRoleId)];
  }, [targetRoles, scopeRoleId]);

  const prompts = useMemo(
    () => buildSuggestedPrompts(profile, prioritizedTargetRoles, gapAnalysis),
    [profile, prioritizedTargetRoles, gapAnalysis],
  );

  const hasConversation = messages.length > 0 || isSending;

  // Both start expanded (2026-08-21, direct request) — a first-time
  // visitor sees the profile snapshot and suggested prompts in full
  // immediately, with nothing to click open first. The moment a real
  // conversation starts (the transition from no messages to the first
  // one, tracked below), both auto-collapse once to reclaim the space
  // the Conversation box needs — from then on they behave as a plain
  // manual toggle again, independent of each other and of conversation
  // state, so the user can still reopen either at any point afterward.
  const [profileOpen, setProfileOpen] = useState(true);
  const [promptsOpen, setPromptsOpen] = useState(true);
  const hadConversationRef = useRef(false);
  useEffect(() => {
    if (hasConversation && !hadConversationRef.current) {
      setProfileOpen(false);
      setPromptsOpen(false);
    }
    hadConversationRef.current = hasConversation;
  }, [hasConversation]);

  // AppShell.tsx's own auto-scroll-to-bottom effect targets the page's
  // shared <main> scroll container, which no longer grows with each new
  // message now that the conversation lives in its own bounded,
  // internally-scrolling box (see the Conversation CardContent below) —
  // this box needs the same "reveal the newest message" behavior scoped
  // to itself instead.
  const conversationScrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = conversationScrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, isSending]);
  const gapForActiveRole = (gapAnalysis?.target_role_gaps ?? []).find(
    (gap) => gap.target_role_id === scopeRoleId,
  );
  // Scoped to the active role's own gap count once a role is active —
  // otherwise (Master) the overall count across every target role, same
  // as before this page had any scope awareness.
  const totalGaps = scopeRoleId
    ? (gapForActiveRole?.missing_skills.length ?? 0)
    : (gapAnalysis?.target_role_gaps ?? []).reduce((sum, gap) => sum + gap.missing_skills.length, 0);

  return (
    <div className="flex flex-col gap-6">
      {/* Header/profile-snapshot/suggestions stay visible and pinned to
       * the top of the page's own scroll container (`sticky top-0`)
       * regardless of conversation state (2026-08-21, direct request) —
       * they used to be conditionally removed the moment a conversation
       * started (`!hasConversation`), which made both cards vanish the
       * instant someone clicked a suggested prompt. The Conversation
       * card below is the only part that scrolls internally now (see
       * its own CardContent), so this block never gets pushed off-screen
       * by a growing message list either. */}
      <div className="sticky top-0 z-10 flex flex-col gap-6 bg-[hsl(var(--center-bg))] pb-2">
        <Card>
          <CardContent className="flex items-center gap-4 pt-6">
            <div
              className={cn(
                "flex h-12 w-12 shrink-0 items-center justify-center rounded-full",
                RAINBOW_GRADIENT,
              )}
            >
              <Bot className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="font-display text-lg font-semibold">Your AI Career Coach</h1>
              <p className="text-sm text-muted-foreground">
                Ask about your next role, closing skill gaps, or how to tell your career story —
                type below to get started, or pick a starting point.
              </p>
            </div>
          </CardContent>
        </Card>

        <CollapsibleCard
          title="Your profile at a glance"
          headerExtra={
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              Showing:
              <Link
                to={scopeRoleId ? `/profile?role=${scopeRoleId}` : "/profile"}
                aria-label={`Go to ${activeRole ? activeRole.role_name : "Master Profile"}`}
                onClick={(event) => event.stopPropagation()}
                className="transition-opacity hover:opacity-80"
              >
                <Badge variant="accent">{activeRole ? activeRole.role_name : "Master Profile"}</Badge>
              </Link>
            </div>
          }
          isOpen={profileOpen}
          onToggle={() => setProfileOpen((v) => !v)}
        >
          <CardContent className="flex flex-wrap gap-x-8 gap-y-4 text-sm">
            <div>
              <p className="text-muted-foreground">Headline</p>
              {profile?.headline ? (
                <RichTextDisplay html={profile.headline} className="font-medium" />
              ) : (
                <p className="font-medium">Not set yet</p>
              )}
            </div>
            <div>
              <p className="text-muted-foreground">Target roles</p>
              <p className="font-medium">{targetRoles?.length ?? 0}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Skills tracked</p>
              <p className="font-medium">{profile?.core_competencies.length ?? 0}</p>
            </div>
            <div>
              <p className="text-muted-foreground">
                {activeRole ? `${activeRole.role_name} skill gaps` : "Open skill gaps"}
              </p>
              <p className="font-medium">{totalGaps}</p>
            </div>
          </CardContent>
        </CollapsibleCard>

        <CollapsibleCard
          title="Not sure where to start?"
          isOpen={promptsOpen}
          onToggle={() => setPromptsOpen((v) => !v)}
        >
          <CardContent className="grid gap-2 sm:grid-cols-2">
            {prompts.map((suggestion) => (
              <button
                key={suggestion.label}
                type="button"
                onClick={() => sendTurn(suggestion.prompt)}
                disabled={isSending}
                className="rounded-md border border-border p-3 text-left text-sm transition-colors hover:border-transparent hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
              >
                <p className="font-medium">{suggestion.label}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{suggestion.prompt}</p>
              </button>
            ))}
          </CardContent>
        </CollapsibleCard>
      </div>

      {hasConversation && (
        <Card>
          <CardHeader className="flex-row items-start justify-between space-y-0">
            <CardTitle>Conversation</CardTitle>
            <div className="flex items-center gap-1">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setClearConfirmOpen(true)}
              >
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
        </Card>
      )}

      {isError && (
        <p role="alert" className="text-sm text-destructive">
          {getErrorMessage(error)}
        </p>
      )}

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
    </div>
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

/** Same rationale as ChatThread.tsx's TypingIndicator — real LLM calls can
 * take several seconds, so this is the only signal of in-progress work. */
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
