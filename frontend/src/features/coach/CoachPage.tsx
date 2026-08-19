import { useCareerProfile, useTargetRoles } from "@/api/queries/career-profile";
import { useGapAnalysis } from "@/api/queries/skill-intelligence";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RichTextDisplay } from "@/components/ui/rich-text-editor";
import { buildSuggestedPrompts } from "@/features/coach/suggested-prompts";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { useChatComposer } from "@/hooks/useChatComposer";
import { useChatStore } from "@/stores/chat-store";
import type { ChatThreadMessage } from "@/stores/chat-store";
import { Sparkles, UserCircle } from "lucide-react";
import { useMemo } from "react";

const RAINBOW_GRADIENT =
  "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]";

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
 */
export function CoachPage() {
  const { data: profile } = useCareerProfile();
  const { data: targetRoles } = useTargetRoles();
  const { data: gapAnalysis } = useGapAnalysis();

  const messages = useChatStore((state) => state.messages);
  const isSending = useChatStore((state) => state.isSending);
  const { sendTurn, isError, error } = useChatComposer();

  const prompts = useMemo(
    () => buildSuggestedPrompts(profile, targetRoles, gapAnalysis),
    [profile, targetRoles, gapAnalysis],
  );

  const hasConversation = messages.length > 0 || isSending;
  const totalGaps = (gapAnalysis?.target_role_gaps ?? []).reduce(
    (sum, gap) => sum + gap.missing_skills.length,
    0,
  );

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardContent className="flex items-center gap-4 pt-6">
          <div
            className={cn(
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-full",
              RAINBOW_GRADIENT,
            )}
          >
            <Sparkles className="h-6 w-6 text-primary" />
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

      {!hasConversation && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Your profile at a glance</CardTitle>
            </CardHeader>
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
                <p className="text-muted-foreground">Open skill gaps</p>
                <p className="font-medium">{totalGaps}</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Not sure where to start?</CardTitle>
            </CardHeader>
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
          </Card>
        </>
      )}

      {hasConversation && (
        <Card>
          <CardHeader>
            <CardTitle>Conversation</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
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
    </div>
  );
}

function MessageBubble({ message }: { message: ChatThreadMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex items-start gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-muted text-muted-foreground" : cn(RAINBOW_GRADIENT, "text-primary"),
        )}
      >
        {isUser ? <UserCircle className="h-5 w-5" /> : <Sparkles className="h-4 w-4" />}
      </div>
      <div className={cn("flex max-w-2xl flex-col gap-1", isUser && "items-end")}>
        <span className="text-xs font-medium text-muted-foreground">
          {isUser ? "You" : "AI Career Coach"}
        </span>
        <div
          className={cn(
            "whitespace-pre-wrap rounded-lg px-4 py-2.5 text-sm",
            isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground",
          )}
        >
          {message.content}
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
        <Sparkles className="h-4 w-4" />
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
