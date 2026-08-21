import {
  useClearJdTailoringMessages,
  useDeleteJdTailoringMessage,
  useDeleteJdTailoringSession,
  useGenerateTailoredResume,
  useJdTailoringMessages,
  useJdTailoringSessions,
  useSendJdTailoringMessage,
} from "@/api/queries/jd-tailoring";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { InlineLink } from "@/components/ui/inline-link";
import { Textarea } from "@/components/ui/textarea";
import { formatDisplayDateTime, formatRelativeTime } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { renderMarkdownMessage } from "@/lib/markdown-message";
import { cn } from "@/lib/utils";
import { Bot, Eraser, Trash2, UserCircle } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

type JdTailoringMessage = components["schemas"]["JdTailoringMessageResponse"];

const RAINBOW_GRADIENT =
  "bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]";

/**
 * The dedicated JD Tailoring chat page — a genuinely separate
 * multi-turn conversation domain from the global AI Career Coach chat
 * (app/domain/chat/), not a second view onto the same store. Sessions
 * are started from the Opportunity Intelligence page (radio-select a
 * listing + "Evaluate", or "Add Your Own JD") and land here for the
 * full conversation. Selection is tracked via ?session= so a session
 * link is shareable within the SPA session (not across a hard reload —
 * this app's access token is deliberately in-memory only).
 */
export function JdTailoringPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const sessionId = searchParams.get("session");

  const { data: sessions, isLoading: sessionsLoading } = useJdTailoringSessions();
  const { data: messages, isLoading: messagesLoading } = useJdTailoringMessages(sessionId);
  const sendMessage = useSendJdTailoringMessage(sessionId ?? "");
  const deleteSession = useDeleteJdTailoringSession();
  const clearMessages = useClearJdTailoringMessages();
  const deleteMessage = useDeleteJdTailoringMessage(sessionId ?? "");
  const generateResume = useGenerateTailoredResume(sessionId ?? "");

  const [draft, setDraft] = useState("");
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [clearMessagesConfirmOpen, setClearMessagesConfirmOpen] = useState(false);
  const [deleteMessageTargetId, setDeleteMessageTargetId] = useState<string | null>(null);

  const selectedSession = sessions?.find((session) => session.id === sessionId) ?? null;

  function selectSession(id: string) {
    setSearchParams({ session: id });
  }

  function handleSend() {
    if (!sessionId || !draft.trim() || sendMessage.isPending) return;
    sendMessage.mutate({ content: draft }, { onSuccess: () => setDraft("") });
  }

  function handleConfirmDelete() {
    if (!deleteTargetId) return;
    const wasSelected = deleteTargetId === sessionId;
    deleteSession.mutate(deleteTargetId, {
      onSuccess: () => {
        if (wasSelected) setSearchParams({});
        setDeleteTargetId(null);
      },
    });
  }

  function handleConfirmClearMessages() {
    if (!sessionId) return;
    clearMessages.mutate(sessionId, {
      onSuccess: () => setClearMessagesConfirmOpen(false),
    });
  }

  function handleConfirmDeleteMessage() {
    if (!deleteMessageTargetId) return;
    deleteMessage.mutate(deleteMessageTargetId, {
      onSuccess: () => setDeleteMessageTargetId(null),
    });
  }

  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
      <Card className="lg:w-80 lg:shrink-0">
        <CardHeader>
          <CardTitle>Sessions</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {sessionsLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
          {sessions && sessions.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No sessions yet — start one from a Job Listing on the{" "}
              <InlineLink to="/opportunities">Opportunity Intelligence</InlineLink> page, or use
              "Add Your Own JD" there.
            </p>
          )}
          {sessions?.map((session) => (
            <div
              key={session.id}
              className={cn(
                "flex items-start justify-between gap-2 rounded-md border px-3 py-2",
                session.id === sessionId
                  ? "border-accent bg-accent/5"
                  : "border-border hover:bg-muted/50",
              )}
            >
              <button
                type="button"
                onClick={() => selectSession(session.id)}
                className="flex-1 text-left"
              >
                <p className="text-sm font-medium">{session.source_title ?? "Custom JD"}</p>
                {session.source_company && (
                  <p className="text-xs text-muted-foreground">
                    {session.source_company}
                    {session.source_type === "custom" ? " (custom)" : ""}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">
                  {formatDisplayDateTime(session.created_at)}
                </p>
              </button>
              <button
                type="button"
                onClick={() => setDeleteTargetId(session.id)}
                aria-label="Delete session"
                className="shrink-0 p-1 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="flex-1">
        {!selectedSession ? (
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              Select a session from the list, or start a new one from a Job Listing on{" "}
              <InlineLink to="/opportunities">Opportunity Intelligence</InlineLink>.
            </p>
          </CardContent>
        ) : (
          <>
            <CardHeader className="flex-row items-start justify-between space-y-0">
              <CardTitle>
                {selectedSession.source_title ?? "Custom JD"}
                {selectedSession.source_company ? ` at ${selectedSession.source_company}` : ""}
              </CardTitle>
              {!!messages?.length && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setClearMessagesConfirmOpen(true)}
                >
                  <Eraser className="h-3.5 w-3.5" />
                  Clear conversation
                </Button>
              )}
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <details className="rounded-md border border-border p-3 text-sm">
                <summary className="cursor-pointer font-medium text-muted-foreground">
                  Job description
                </summary>
                <p className="mt-2 whitespace-pre-wrap text-sm">{selectedSession.jd_text}</p>
              </details>

              <div className="flex flex-col gap-2 rounded-md border border-border p-3">
                <p className="text-sm font-medium">Tailored Resume</p>
                <p className="text-xs text-muted-foreground">
                  Generates a resume rewritten to emphasize what this JD is looking for — its own
                  file, separate from your profile's regular downloadable resume.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={generateResume.isPending}
                    onClick={() => generateResume.mutate("docx")}
                  >
                    {generateResume.isPending && generateResume.variables === "docx"
                      ? "Generating..."
                      : selectedSession.tailored_resume_docx_url
                        ? "Regenerate Word"
                        : "Generate Word"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={generateResume.isPending}
                    onClick={() => generateResume.mutate("pdf")}
                  >
                    {generateResume.isPending && generateResume.variables === "pdf"
                      ? "Generating..."
                      : selectedSession.tailored_resume_pdf_url
                        ? "Regenerate PDF"
                        : "Generate PDF"}
                  </Button>
                </div>
                {(selectedSession.tailored_resume_docx_url ||
                  selectedSession.tailored_resume_pdf_url) && (
                  <div className="flex flex-wrap gap-3">
                    {selectedSession.tailored_resume_docx_url && (
                      <a
                        href={selectedSession.tailored_resume_docx_url}
                        className="text-sm text-accent hover:underline"
                      >
                        View Word
                      </a>
                    )}
                    {selectedSession.tailored_resume_pdf_url && (
                      <a
                        href={selectedSession.tailored_resume_pdf_url}
                        className="text-sm text-accent hover:underline"
                      >
                        View PDF
                      </a>
                    )}
                  </div>
                )}
                {selectedSession.tailored_resume_status === "failed" &&
                  selectedSession.tailored_resume_error && (
                    <p role="alert" className="text-sm text-destructive">
                      {/* Prefixed with when this happened — the error
                          text itself can bake in a real-time-only hint
                          (e.g. "Try again in about 25 seconds"), which
                          reads as flatly wrong once shown again later
                          with nothing marking it as a past attempt, not
                          a live one (confirmed live, 2026-08-20: a real
                          user report of a Groq rate-limit message
                          "stuck" on screen across many logout/login
                          cycles — it's real persisted session state, not
                          a stale UI artifact, and only clears once a
                          fresh Generate/Regenerate attempt overwrites it). */}
                      {selectedSession.tailored_resume_generated_at && (
                        <span className="font-medium">
                          Last attempt ({formatRelativeTime(selectedSession.tailored_resume_generated_at)}
                          ):{" "}
                        </span>
                      )}
                      {selectedSession.tailored_resume_error}
                    </p>
                  )}
                {selectedSession.tailored_resume_generated_at && (
                  <p className="text-xs text-muted-foreground">
                    Last generated{" "}
                    {formatDisplayDateTime(selectedSession.tailored_resume_generated_at)}
                  </p>
                )}
              </div>

              <div className="flex flex-col gap-4">
                {messagesLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
                {messages?.length === 0 && !messagesLoading && (
                  <p className="text-sm text-muted-foreground">
                    Ask about how well you match this JD, or how to tailor your resume for it.
                  </p>
                )}
                {messages?.map((message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    onDelete={() => setDeleteMessageTargetId(message.id)}
                  />
                ))}
                {sendMessage.isPending && <TypingBubble />}
              </div>

              {sendMessage.isError && (
                <p role="alert" className="text-sm text-destructive">
                  {getErrorMessage(sendMessage.error)}
                </p>
              )}

              <div className="flex flex-col gap-2 border-t border-border pt-4">
                <Textarea
                  rows={3}
                  placeholder="Ask about your fit, or how to tailor your resume..."
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <div className="flex justify-end">
                  <Button
                    type="button"
                    onClick={handleSend}
                    disabled={!draft.trim() || sendMessage.isPending}
                  >
                    {sendMessage.isPending ? "Sending..." : "Send"}
                  </Button>
                </div>
              </div>
            </CardContent>
          </>
        )}
      </Card>

      <ConfirmDialog
        open={deleteTargetId !== null}
        onCancel={() => setDeleteTargetId(null)}
        onConfirm={handleConfirmDelete}
        title="Delete this session?"
        description="This removes the JD Tailoring conversation. Any Job Application it created stays tracked, just unlinked from this session."
        isPending={deleteSession.isPending}
      />

      <ConfirmDialog
        open={clearMessagesConfirmOpen}
        onCancel={() => setClearMessagesConfirmOpen(false)}
        onConfirm={handleConfirmClearMessages}
        title="Clear this conversation?"
        description="Removes every message in this conversation — the session itself (the JD, and any generated tailored resume) stays. This can't be undone."
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
        isPending={clearMessages.isPending}
      />

      <ConfirmDialog
        open={deleteMessageTargetId !== null}
        onCancel={() => setDeleteMessageTargetId(null)}
        onConfirm={handleConfirmDeleteMessage}
        title="Delete this message?"
        description="Removes just this one message — the rest of the conversation stays. This can't be undone."
        isPending={deleteMessage.isPending}
      />
    </div>
  );
}

function MessageBubble({
  message,
  onDelete,
}: {
  message: JdTailoringMessage;
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
            {isUser ? "You" : "Advisor"}
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

/** Same rationale as CoachPage.tsx's TypingBubble — real LLM calls can
 * take several seconds, so this is the only signal of in-progress work. */
function TypingBubble() {
  return (
    <div className="flex items-start gap-3" role="status" aria-label="Advisor is thinking">
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
