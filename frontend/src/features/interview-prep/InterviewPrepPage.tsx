import { useTargetRoles } from "@/api/queries/career-profile";
import {
  useInterviewPrepSummary,
  useInterviewQuestions,
  useInterviewTopics,
} from "@/api/queries/interview-prep";
import type { components } from "@/api/schema.gen";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TabStrip } from "@/components/ui/tab-strip";
import { InterviewQuestionsSection } from "@/features/interview-prep/InterviewQuestionsSection";
import { groupInterviewQuestionsByCategory } from "@/lib/group-interview-questions-by-category";
import { scrollToAfterPaint } from "@/lib/scroll-to-after-paint";
import { cn } from "@/lib/utils";
import { useRoleScopeParam } from "@/stores/target-role-scope-store";
import { type ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

/**
 * Interview Preparation — scoped either to the Master profile (generic
 * prep) or a specific Target Role, the same split Career Profile itself
 * uses. `?role=` in the URL (not local state) so the current scope
 * survives a page refresh and is shareable, mirroring
 * CareerProfilePage.tsx's own convention — implemented locally here
 * rather than via the full ProfileScopeProvider Context built for that
 * page's ~8 section components.
 *
 * The nav link always points at the bare `/interview-prep` (no `role`),
 * so without this the scope would silently reset to Master every time
 * — instead, landing here with no `role` param restores whatever role
 * is currently active app-wide (see target-role-scope-store.ts — set
 * from here, Career Profile, Resume Intelligence, Opportunity
 * Intelligence, or Learning Intelligence, whichever was most recently
 * changed). An explicit `?role=` in the URL (a bookmark, a link someone
 * shared) always wins over the stored preference — only a *bare*
 * landing falls back to it.
 */
export function InterviewPrepPage() {
  const { targetRoleId, searchParams, setSearchParams } = useRoleScopeParam();
  const scopeKey = targetRoleId ?? "master";
  const { data: targetRoles } = useTargetRoles();

  const { data: topics } = useInterviewTopics(targetRoleId);
  const { data: questions } = useInterviewQuestions(targetRoleId);
  const { data: summary } = useInterviewPrepSummary();

  // Interview Questions stays here; Articles now live in Knowledge Hub.
  const [questionCategoryFilter, setQuestionCategoryFilter] = useState<string | null>("all");
  useEffect(() => {
    setQuestionCategoryFilter("all");
  }, [scopeKey]);

  const questionGroups = groupInterviewQuestionsByCategory(questions ?? []);

  const questionSubTabs: { id: string | null; label: string }[] =
    questionGroups.length > 1
      ? [
          { id: "all", label: "All" },
          ...questionGroups.map((group) => ({
            id: group.category,
            label: group.category ?? "Uncategorized",
          })),
        ]
      : [];

  const [expandedQuestionId, setExpandedQuestionId] = useState<string | null>(null);

  // A follow-up only renders while its parent question is open, so its
  // expanded state is independent from the primary question accordion.
  const [expandedFollowUpId, setExpandedFollowUpId] = useState<string | null>(null);

  // Preserve other query parameters when the selected scope changes.
  function handleScopeChange(value: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set("role", value);
      else next.delete("role");
      return next;
    });
  }

  function openQuestion(id: string) {
    setExpandedQuestionId(id);
    scrollToAfterPaint(`interview-question-${id}`);
  }

  // A follow-up only ever renders while its own parent question is
  // open (see InterviewQuestionsSection.tsx), so selecting one from the
  // TOC has to force both open together, not just the follow-up itself.
  function openFollowUp(followUpId: string, parentQuestionId: string) {
    setExpandedQuestionId(parentQuestionId);
    setExpandedFollowUpId(followUpId);
    scrollToAfterPaint(`interview-question-${followUpId}`);
  }

  if (searchParams.get("tab") === "topics") {
    const params = new URLSearchParams(searchParams);
    params.delete("tab");
    const query = params.toString();
    return <Navigate to={`/knowledge-hub${query ? `?${query}` : ""}`} replace />;
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardContent className="flex flex-col gap-3 pt-6">
          <div className="flex flex-col gap-1.5">
            <Label
              htmlFor="interview-prep-scope"
              className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
            >
              Current Scope
            </Label>
            <Select
              id="interview-prep-scope"
              className="w-72"
              value={targetRoleId ?? ""}
              onChange={(e) => handleScopeChange(e.target.value)}
            >
              <option value="">Master (generic)</option>
              {targetRoles?.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.role_name}
                </option>
              ))}
            </Select>
          </div>
          {summary && summary.scopes.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {summary.scopes.map((s, i) => (
                <span key={s.target_role_id ?? "master"}>
                  {i > 0 && " | "}
                  <span className="font-medium text-foreground">{s.role_name}:</span>{" "}
                  {s.question_count}{" "}
                  {s.question_count === 1 ? "question" : "questions"}
                </span>
              ))}
            </p>
          )}
        </CardContent>
      </Card>

      {questionSubTabs.length > 0 && (
        <TabStrip
          tabs={questionSubTabs}
          activeId={questionCategoryFilter}
          onChange={setQuestionCategoryFilter}
          ariaLabel="Filter questions by category"
          size="sm"
        />
      )}
      <QuestionsTableOfContents
        questions={questions ?? []}
        categoryFilter={questionCategoryFilter}
        onSelectQuestion={openQuestion}
        onSelectFollowUp={openFollowUp}
      />
      <InterviewQuestionsSection
        key={`${scopeKey}-questions`}
        scope={targetRoleId}
        topics={topics ?? []}
        targetRoles={targetRoles ?? []}
        expandedId={expandedQuestionId}
        setExpandedId={setExpandedQuestionId}
        expandedFollowUpId={expandedFollowUpId}
        setExpandedFollowUpId={setExpandedFollowUpId}
        categoryFilter={questionCategoryFilter}
        totalCount={summary?.total_question_count}
      />
    </div>
  );
}

/** "Content" for a question/follow-up is a prepared answer — either
 * the user's own or a real generated one. Mirrors the exact same
 * truthy checks InterviewQuestionsSection.tsx's own "No answer yet"/
 * "No AI answer generated yet" empty states already use, just combined
 * into one signal for the TOC's red-if-nothing-prepared highlight. */
function questionHasContent(question: components["schemas"]["InterviewQuestionResponse"]): boolean {
  return !!question.manual_answer || question.ai_answer_status === "generated";
}

function QuestionsTableOfContents({
  questions,
  categoryFilter,
  onSelectQuestion,
  onSelectFollowUp,
}: {
  questions: components["schemas"]["InterviewQuestionResponse"][];
  categoryFilter: string | null;
  onSelectQuestion: (id: string) => void;
  onSelectFollowUp: (followUpId: string, parentQuestionId: string) => void;
}) {
  const questionGroups = groupInterviewQuestionsByCategory(questions);
  const visibleGroups =
    categoryFilter === "all"
      ? questionGroups
      : questionGroups.filter((group) => group.category === categoryFilter);
  if (visibleGroups.length === 0) return null;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Table of Contents
        </p>
        <div className="flex flex-col gap-2">
          {visibleGroups.map((group) => (
            <div key={group.category ?? "__uncategorized"}>
              {group.category && (
                <p className="text-xs font-medium text-muted-foreground">{group.category}:</p>
              )}
              <ul className="list-disc space-y-1 pl-5">
                {group.questions.map((question) => (
                  <li key={question.id}>
                    <TocEntryLink
                      onSelect={() => onSelectQuestion(question.id)}
                      hasContent={questionHasContent(question)}
                    >
                      {question.question}
                    </TocEntryLink>
                    {question.follow_ups.length > 0 && (
                      <ul className="list-disc space-y-1 pl-5">
                        {question.follow_ups.map((followUp) => (
                          <li key={followUp.id}>
                            <TocEntryLink
                              onSelect={() => onSelectFollowUp(followUp.id, question.id)}
                              hasContent={questionHasContent(followUp)}
                            >
                              {followUp.question}
                            </TocEntryLink>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/** A `<span role="button">`, not a real `<button>` — confirmed live that a
 * `<button>` inside a `<li>` misaligns the list's ::marker to the bottom
 * of the item once its text wraps to multiple lines, in a way that
 * persists even with `display: inline` and `appearance: none` forced via
 * inline style (a Chromium quirk in how native form controls generate
 * their box, independent of the `display` property). A plain inline
 * element sidesteps it entirely, so this restores real button semantics
 * by hand (role, tabIndex, Enter/Space activation) rather than fighting
 * the browser's own button rendering. */
function TocEntryLink({
  onSelect,
  children,
  hasContent = true,
}: {
  onSelect: () => void;
  children: ReactNode;
  //: Renders in red (text-destructive, this app's standing error/
  //: warning color) when false — a quick visual flag for "nothing
  //: prepared here yet," direct user request. Defaults to true so
  //: nothing has to opt in explicitly for the common, non-empty case.
  hasContent?: boolean;
}) {
  return (
    <span
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      title={hasContent ? undefined : "No content yet"}
      className={cn(
        "cursor-pointer text-left text-sm font-medium underline underline-offset-2",
        hasContent ? "text-accent hover:text-accent/80" : "text-destructive hover:text-destructive/80",
      )}
    >
      {children}
    </span>
  );
}
