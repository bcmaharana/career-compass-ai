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
import { InterviewQuestionsSection } from "@/features/interview-prep/InterviewQuestionsSection";
import { InterviewTopicsSection } from "@/features/interview-prep/InterviewTopicsSection";
import { groupInterviewQuestionsByCategory } from "@/lib/group-interview-questions-by-category";
import { groupInterviewTopicsBySection } from "@/lib/group-interview-topics-by-section";
import {
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useEffect,
  useState,
} from "react";
import { useSearchParams } from "react-router-dom";

/** "master" is a real stored value here (not just an absent key) so a
 * returning visit can tell "Master was the last scope, deliberately"
 * apart from "no preference recorded yet" (a brand-new browser/user) —
 * both currently render identically (no `role` param), but only the
 * former should ever *win* over some other stale state, so they need to
 * stay distinguishable in storage even though they're the same on screen. */
const LAST_SCOPE_KEY = "interview-prep-last-scope";

/**
 * Interview Preparation — scoped either to the Master profile (generic
 * prep) or a specific Target Role, the same split Career Profile itself
 * uses. `?role=` in the URL (not local state) so the current scope
 * survives a page refresh and is shareable, mirroring
 * CareerProfilePage.tsx's own convention — implemented locally here
 * rather than via the full ProfileScopeProvider Context built for that
 * page's ~8 section components, since this page only has two.
 *
 * The nav link always points at the bare `/interview-prep` (no `role`),
 * so without this the scope would silently reset to Master every time
 * — instead, landing here with no `role` param restores whatever scope
 * was last viewed/edited, persisted in localStorage (survives a full
 * browser restart, not just this session). An explicit `?role=` in the
 * URL (a bookmark, a link someone shared) always wins over the stored
 * preference — only a *bare* landing falls back to it.
 */
export function InterviewPrepPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const targetRoleId = searchParams.get("role");
  const scopeKey = targetRoleId ?? "master";
  const { data: targetRoles } = useTargetRoles();

  // Restore-on-bare-landing: runs once per mount, only acts when the
  // URL didn't already specify a scope.
  useEffect(() => {
    if (searchParams.has("role")) return;
    const saved = localStorage.getItem(LAST_SCOPE_KEY);
    if (saved && saved !== "master") {
      setSearchParams({ role: saved }, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist whenever the resolved scope changes — covers both an
  // explicit pick from the dropdown and the restore above.
  useEffect(() => {
    localStorage.setItem(LAST_SCOPE_KEY, targetRoleId ?? "master");
  }, [targetRoleId]);

  const { data: topics } = useInterviewTopics(targetRoleId);
  const { data: questions } = useInterviewQuestions(targetRoleId);
  const { data: summary } = useInterviewPrepSummary();

  // Accordion state for both sections lives here, not inside each
  // section component, so the Table of Contents can force a specific
  // card open (and scroll to it) — see InterviewTopicsSection.tsx's
  // comment on why a TOC click needs force-open semantics, not toggle.
  // A single cross-section value (not two independent booleans) so
  // opening a Topic always closes whatever Question was open and vice
  // versa — only ever one card open across both sections at once.
  const [expandedItem, setExpandedItem] = useState<{ type: "topic" | "question"; id: string } | null>(
    null,
  );

  // Adapters presenting the shared cross-section state as the plain
  // `string | null` + `Dispatch<SetStateAction<string | null>>` shape
  // InterviewTopicsSection/InterviewQuestionsSection already expect —
  // each section's own toggle-if-already-open logic
  // (`setExpandedId(prev => prev === id ? null : id)`) keeps working
  // unchanged; opening one via either adapter naturally clears the
  // other since they share one underlying value.
  const expandedTopicId = expandedItem?.type === "topic" ? expandedItem.id : null;
  const expandedQuestionId = expandedItem?.type === "question" ? expandedItem.id : null;

  const setExpandedTopicId: Dispatch<SetStateAction<string | null>> = (action) => {
    setExpandedItem((prev) => {
      const prevId = prev?.type === "topic" ? prev.id : null;
      const nextId = typeof action === "function" ? action(prevId) : action;
      return nextId === null ? null : { type: "topic", id: nextId };
    });
  };

  const setExpandedQuestionId: Dispatch<SetStateAction<string | null>> = (action) => {
    setExpandedItem((prev) => {
      const prevId = prev?.type === "question" ? prev.id : null;
      const nextId = typeof action === "function" ? action(prevId) : action;
      return nextId === null ? null : { type: "question", id: nextId };
    });
  };

  // A separate, single-open accordion for follow-up questions —
  // "closed automatically when other [follow-up] cards are clicked,
  // similar behavior as primary question" (direct user request). Kept
  // independent from expandedItem above rather than folded into it: a
  // follow-up only ever renders while its own parent question is
  // already open, so there's no "does opening this follow-up need to
  // close a Topic" case to reconcile the way Topic vs. Question does —
  // it only ever needs to close whichever *other* follow-up was open.
  const [expandedFollowUpId, setExpandedFollowUpId] = useState<string | null>(null);

  function handleScopeChange(value: string) {
    if (value) setSearchParams({ role: value });
    else setSearchParams({});
  }

  function openTopic(id: string) {
    setExpandedItem({ type: "topic", id });
    scrollToAfterPaint(`interview-topic-${id}`);
  }

  function openQuestion(id: string) {
    setExpandedItem({ type: "question", id });
    scrollToAfterPaint(`interview-question-${id}`);
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
          {summary && summary.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {summary.map((s, i) => (
                <span key={s.target_role_id ?? "master"}>
                  {i > 0 && " | "}
                  <span className="font-medium text-foreground">{s.role_name}:</span>{" "}
                  {s.topic_count} {s.topic_count === 1 ? "topic" : "topics"}, {s.question_count}{" "}
                  {s.question_count === 1 ? "question" : "questions"}
                </span>
              ))}
            </p>
          )}
        </CardContent>
      </Card>

      <TableOfContents
        topics={topics ?? []}
        questions={questions ?? []}
        onSelectTopic={openTopic}
        onSelectQuestion={openQuestion}
      />

      {/* Keyed by scope so switching between Master and a Target Role
          fully remounts both sections instead of leaking edit-mode/
          collapse state across scopes — same fix CLAUDE.md documents
          for the equivalent Career Profile bug. Resetting the lifted
          accordion state on scope change too, for the same reason. */}
      <InterviewTopicsSection
        key={`${scopeKey}-topics`}
        scope={targetRoleId}
        targetRoles={targetRoles ?? []}
        expandedId={expandedTopicId}
        setExpandedId={setExpandedTopicId}
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
      />
    </div>
  );
}

/** Scrolls to an element once the browser has actually painted the
 * state update that (likely) just expanded it — a single
 * requestAnimationFrame can still fire before layout reflects a just-
 * expanded accordion card, so this waits two frames, a standard
 * "wait for the next real paint" pattern. */
function scrollToAfterPaint(elementId: string) {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.getElementById(elementId)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function TableOfContents({
  topics,
  questions,
  onSelectTopic,
  onSelectQuestion,
}: {
  topics: components["schemas"]["InterviewTopicResponse"][];
  questions: components["schemas"]["InterviewQuestionResponse"][];
  onSelectTopic: (id: string) => void;
  onSelectQuestion: (id: string) => void;
}) {
  if (topics.length === 0 && questions.length === 0) return null;

  const groups = groupInterviewTopicsBySection(topics);
  const questionGroups = groupInterviewQuestionsByCategory(questions);

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Table of Contents
        </p>
        {groups.length > 0 && (
          <div className="flex flex-col gap-2">
            {groups.map((group) => (
              <div key={group.section ?? "__ungrouped"}>
                {group.section && (
                  <p className="text-xs font-medium text-muted-foreground">{group.section}:</p>
                )}
                <ul className="list-disc space-y-1 pl-5">
                  {group.topics.map((topic) => (
                    <li key={topic.id}>
                      <TocEntryLink onSelect={() => onSelectTopic(topic.id)}>
                        {topic.name}
                      </TocEntryLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
        {questions.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Questions:
            </p>
            {questionGroups.map((group) => (
              <div key={group.category ?? "__uncategorized"}>
                {group.category && (
                  <p className="text-xs font-medium text-muted-foreground">{group.category}:</p>
                )}
                <ul className="list-disc space-y-1 pl-5">
                  {group.questions.map((question) => (
                    <li key={question.id}>
                      <TocEntryLink onSelect={() => onSelectQuestion(question.id)}>
                        {question.question}
                      </TocEntryLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
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
}: {
  onSelect: () => void;
  children: ReactNode;
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
      className="cursor-pointer text-left text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
    >
      {children}
    </span>
  );
}
