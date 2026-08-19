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
import { cn } from "@/lib/utils";
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

/** Tab config for the page's sub-sections — Topics and Interview
 * Questions today, extensible to a future third tab without touching
 * anything but this array and the render switch below it. `"topics"`
 * is the default and is never written into the URL (mirrors the
 * Master-scope-omitted-from-the-URL convention above), so an existing
 * bookmark/shared link with no `tab` param still lands correctly. */
const PREP_TABS = [
  { id: "topics", label: "Topics" },
  { id: "questions", label: "Interview Questions" },
] as const;
type PrepTabId = (typeof PREP_TABS)[number]["id"];

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
  const activeTab: PrepTabId = searchParams.get("tab") === "questions" ? "questions" : "topics";
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

  // Sub-tabs, one level down from Topics/Interview Questions — filters
  // each tab's own Table of Contents + card list down to a single
  // section/category at a time, so a scope with many questions/topics
  // doesn't dump them all into one long scroll (direct user feedback).
  // `"all"` is the default/reset value; a real section/category name
  // filters to just that group, and `null` filters to items with no
  // section/category set at all (the same null-means-ungrouped
  // convention groupInterviewTopicsBySection/
  // groupInterviewQuestionsByCategory already use). Reset to "all"
  // whenever the scope changes — a filter selected under one Target
  // Role's own categories wouldn't necessarily mean anything under a
  // different scope's.
  const [topicSectionFilter, setTopicSectionFilter] = useState<string | null>("all");
  const [questionCategoryFilter, setQuestionCategoryFilter] = useState<string | null>("all");
  useEffect(() => {
    setTopicSectionFilter("all");
    setQuestionCategoryFilter("all");
  }, [scopeKey]);

  const topicGroups = groupInterviewTopicsBySection(topics ?? []);
  const questionGroups = groupInterviewQuestionsByCategory(questions ?? []);

  // Sub-tabs only appear once there's real grouping to filter by — a
  // single group (everything ungrouped, or everything under one shared
  // section/category) means an "All" tab would be redundant with the
  // one real tab sitting next to it.
  const topicSubTabs: { id: string | null; label: string }[] =
    topicGroups.length > 1
      ? [
          { id: "all", label: "All" },
          ...topicGroups.map((group) => ({ id: group.section, label: group.section ?? "Uncategorized" })),
        ]
      : [];
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

  // Preserves whichever of `role`/`tab` the caller isn't changing —
  // `setSearchParams({ role: value })` (the pre-tabs version of this
  // function) replaced the entire query string, which would have
  // silently dropped the tab back to its default every time the scope
  // changed.
  function handleScopeChange(value: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set("role", value);
      else next.delete("role");
      return next;
    });
  }

  function handleTabChange(tab: PrepTabId) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (tab === "topics") next.delete("tab");
      else next.set("tab", tab);
      return next;
    });
  }

  // No tab-switching here (unlike an earlier version of this page) — the
  // Topics/Questions Table of Contents cards are now each scoped to
  // their own tab (see TopicsTableOfContents/QuestionsTableOfContents
  // below), so a TOC entry is only ever reachable while its matching
  // tab is already active.
  function openTopic(id: string) {
    setExpandedItem({ type: "topic", id });
    scrollToAfterPaint(`interview-topic-${id}`);
  }

  function openQuestion(id: string) {
    setExpandedItem({ type: "question", id });
    scrollToAfterPaint(`interview-question-${id}`);
  }

  // A follow-up only ever renders while its own parent question is
  // open (see InterviewQuestionsSection.tsx), so selecting one from the
  // TOC has to force both open together, not just the follow-up itself.
  function openFollowUp(followUpId: string, parentQuestionId: string) {
    setExpandedItem({ type: "question", id: parentQuestionId });
    setExpandedFollowUpId(followUpId);
    scrollToAfterPaint(`interview-question-${followUpId}`);
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

      {/* Main tab strip + its sub-tab strip are grouped into one tight
          `gap-2` block (own doc comment below has the shared visual
          mechanics) rather than sharing the page's own `gap-6` — per
          direct user feedback, the two should read as one connected
          tab hierarchy, not two separately-spaced page sections. The
          sub-tab strip (same TabStrip component, same folder-tab
          design, a smaller `size="sm"` — also direct user feedback) is
          absent entirely when there's nothing real to filter by (see
          topicSubTabs/questionSubTabs above). */}
      <div className="flex flex-col gap-2">
        <TabStrip
          tabs={PREP_TABS}
          activeId={activeTab}
          onChange={handleTabChange}
          ariaLabel="Interview Preparation section"
        />
        {activeTab === "topics" && topicSubTabs.length > 0 && (
          <TabStrip
            tabs={topicSubTabs}
            activeId={topicSectionFilter}
            onChange={setTopicSectionFilter}
            ariaLabel="Filter topics by section"
            size="sm"
          />
        )}
        {activeTab === "questions" && questionSubTabs.length > 0 && (
          <TabStrip
            tabs={questionSubTabs}
            activeId={questionCategoryFilter}
            onChange={setQuestionCategoryFilter}
            ariaLabel="Filter questions by category"
            size="sm"
          />
        )}
      </div>

      {/* Each tab owns its own Table of Contents — Topics' TOC shows
          only topics/sections, Questions' TOC shows only
          questions/categories/follow-ups — rather than one combined
          card sitting above both tabs, per direct user feedback. Only
          the active tab's TOC + section are mounted at a time; the
          other tab's data stays warm in the TanStack Query cache (both
          sections/TOCs read the same query keys the page's own
          useInterviewTopics/useInterviewQuestions calls above already
          populate), so switching tabs back is instant, not a refetch.
          Sections are keyed by scope (in addition to being
          conditionally rendered) so switching between Master and a
          Target Role still fully remounts the active section instead
          of leaking edit-mode/collapse state across scopes — same fix
          CLAUDE.md documents for the equivalent Career Profile bug. */}
      {activeTab === "topics" ? (
        <>
          <TopicsTableOfContents
            topics={topics ?? []}
            sectionFilter={topicSectionFilter}
            onSelectTopic={openTopic}
          />
          <InterviewTopicsSection
            key={`${scopeKey}-topics`}
            scope={targetRoleId}
            targetRoles={targetRoles ?? []}
            expandedId={expandedTopicId}
            setExpandedId={setExpandedTopicId}
            sectionFilter={topicSectionFilter}
          />
        </>
      ) : (
        <>
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
          />
        </>
      )}
    </div>
  );
}

/** Shared by both the page's main Topics/Interview Questions tabs and
 * each tab's own section/category sub-tabs — a folder-style tab strip:
 * a shared `border-b` runs beneath every tab (`border-muted-foreground/30`,
 * deliberately darker than the theme's own `border-border` token — the
 * default read as "very light" per direct user feedback; scoped to just
 * this strip rather than darkening `--border` globally, which would
 * touch every other bordered element in the app); each tab is its own
 * rounded-top-corners rectangle (`rounded-t-lg`, square bottom
 * corners) sitting on that line, with the active one given a
 * card-colored background and left/right/top border so it visually
 * "pops" above the strip like a real tab, while its bottom edge is
 * covered by a rainbow-gradient underline segment instead of an
 * ordinary border. Inactive tabs keep the exact same box shape (a
 * transparent border, not no border) so nothing shifts size when the
 * active tab changes. `T` is `null`-inclusive so a sub-tab strip can
 * represent the "no section/category set" bucket as a real tab (its
 * `id` is `null`, matching groupInterviewTopicsBySection/
 * groupInterviewQuestionsByCategory's own null-means-ungrouped
 * convention) without a separate sentinel string. `size="sm"` (used by
 * every sub-tab strip, per direct user feedback) shrinks the text/
 * padding a step below the main tabs' default, so the two levels read
 * as a hierarchy rather than two rows of equally-weighted tabs. */
function TabStrip<T extends string | null>({
  tabs,
  activeId,
  onChange,
  ariaLabel,
  size = "md",
}: {
  tabs: readonly { id: T; label: string }[];
  activeId: T;
  onChange: (id: T) => void;
  ariaLabel: string;
  size?: "md" | "sm";
}) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="flex items-end gap-1 border-b border-muted-foreground/30"
    >
      {tabs.map((tab) => (
        <button
          key={tab.id ?? "__null__"}
          type="button"
          role="tab"
          aria-selected={activeId === tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            "relative -mb-px rounded-t-lg border border-b-0 font-medium transition-colors",
            size === "sm" ? "px-3 py-1 text-xs" : "px-4 py-2 text-sm",
            activeId === tab.id
              ? "border-border bg-card text-foreground"
              : "border-transparent text-muted-foreground hover:bg-muted/60 hover:text-foreground",
          )}
        >
          {tab.label}
          {activeId === tab.id && (
            <span className="absolute inset-x-0 -bottom-px h-0.5 bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]" />
          )}
        </button>
      ))}
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

/** "Content" for a question/follow-up is a prepared answer — either
 * the user's own or a real generated one. Mirrors the exact same
 * truthy checks InterviewQuestionsSection.tsx's own "No answer yet"/
 * "No AI answer generated yet" empty states already use, just combined
 * into one signal for the TOC's red-if-nothing-prepared highlight. */
function questionHasContent(question: components["schemas"]["InterviewQuestionResponse"]): boolean {
  return !!question.manual_answer || question.ai_answer_status === "generated";
}

function TopicsTableOfContents({
  topics,
  sectionFilter,
  onSelectTopic,
}: {
  topics: components["schemas"]["InterviewTopicResponse"][];
  sectionFilter: string | null;
  onSelectTopic: (id: string) => void;
}) {
  const groups = groupInterviewTopicsBySection(topics);
  const visibleGroups =
    sectionFilter === "all" ? groups : groups.filter((group) => group.section === sectionFilter);
  if (visibleGroups.length === 0) return null;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Table of Contents
        </p>
        <div className="flex flex-col gap-2">
          {visibleGroups.map((group) => (
            <div key={group.section ?? "__ungrouped"}>
              {group.section && (
                <p className="text-xs font-medium text-muted-foreground">{group.section}:</p>
              )}
              <ul className="list-disc space-y-1 pl-5">
                {group.topics.map((topic) => (
                  <li key={topic.id}>
                    <TocEntryLink
                      onSelect={() => onSelectTopic(topic.id)}
                      hasContent={!!topic.discussion}
                    >
                      {topic.name}
                    </TocEntryLink>
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
