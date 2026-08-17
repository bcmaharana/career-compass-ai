import {
  useAddFollowUpQuestion,
  useCreateInterviewQuestion,
  useDeleteFollowUpQuestion,
  useDeleteInterviewQuestion,
  useGenerateInterviewAnswer,
  useInterviewQuestions,
  useMoveFollowUpQuestion,
  useMoveInterviewQuestion,
  useUpdateFollowUpQuestion,
  useUpdateInterviewQuestion,
} from "@/api/queries/interview-prep";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { RichTextDisplay, RichTextEditor } from "@/components/ui/rich-text-editor";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { DeleteScopeChoiceDialog } from "@/features/interview-prep/DeleteScopeChoiceDialog";
import { ScopeTagSelector, type ScopeOption } from "@/features/interview-prep/ScopeTagSelector";
import { groupInterviewQuestionsByCategory } from "@/lib/group-interview-questions-by-category";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Pencil, Plus, RefreshCw, Sparkles, Trash2, X } from "lucide-react";
import { type Dispatch, type FormEvent, type SetStateAction, useState } from "react";

type InterviewTopic = components["schemas"]["InterviewTopicResponse"];
type InterviewQuestion = components["schemas"]["InterviewQuestionResponse"];
type ReferenceLink = components["schemas"]["ReferenceLinkPayload"];
type TargetRole = components["schemas"]["TargetRoleResponse"];

interface FormState {
  question: string;
  topic_id: string;
  category: string;
  scopeTargetRoleIds: (string | null)[];
}

/** Scope label for a delete-choice dialog's "Remove from X only" —
 * "Master" for null, the role's name otherwise. */
function scopeLabelFor(targetRoleId: string | null, targetRoles: TargetRole[]): string {
  if (targetRoleId === null) return "Master";
  return targetRoles.find((r) => r.id === targetRoleId)?.role_name ?? "this role";
}

export function InterviewQuestionsSection({
  scope,
  topics,
  targetRoles,
  expandedId,
  setExpandedId,
  expandedFollowUpId,
  setExpandedFollowUpId,
}: {
  scope: string | null;
  topics: InterviewTopic[];
  targetRoles: TargetRole[];
  // Accordion state, lifted up to InterviewPrepPage — see the matching
  // comment in InterviewTopicsSection.tsx for why.
  expandedId: string | null;
  setExpandedId: Dispatch<SetStateAction<string | null>>;
  // Same idea, one level down — a single follow-up open at a time,
  // across every question's own follow-ups list (see
  // InterviewPrepPage.tsx's own comment on why this is a separate
  // piece of state rather than folded into expandedItem).
  expandedFollowUpId: string | null;
  setExpandedFollowUpId: Dispatch<SetStateAction<string | null>>;
}) {
  const { data: questions, isLoading } = useInterviewQuestions(scope);
  const addQuestion = useCreateInterviewQuestion(scope);
  const updateQuestion = useUpdateInterviewQuestion(scope);
  const deleteQuestion = useDeleteInterviewQuestion(scope);
  const moveQuestion = useMoveInterviewQuestion(scope);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>({
    question: "",
    topic_id: "",
    category: "",
    scopeTargetRoleIds: [scope],
  });
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<InterviewQuestion | null>(null);

  const scopeOptions: ScopeOption[] = [
    { id: null, label: "Master (generic)" },
    ...targetRoles.map((r) => ({ id: r.id, label: r.role_name })),
  ];

  function toggleExpanded(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  function openAddDialog() {
    setEditingId(null);
    setForm({ question: "", topic_id: "", category: "", scopeTargetRoleIds: [scope] });
    setDialogOpen(true);
  }

  function openEditDialog(question: InterviewQuestion) {
    setEditingId(question.id);
    setForm({
      question: question.question,
      topic_id: question.topic_id ?? "",
      category: question.category ?? "",
      scopeTargetRoleIds: question.scope_target_role_ids,
    });
    setDialogOpen(true);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const topicId = form.topic_id || null;
    const category = form.category.trim() || null;
    if (editingId) {
      const existing = questions?.find((q) => q.id === editingId);
      updateQuestion
        .mutateAsync({
          id: editingId,
          body: {
            question: form.question,
            topic_id: topicId,
            category,
            manual_answer: existing?.manual_answer ?? null,
            reference_links: existing?.reference_links ?? [],
            scope_target_role_ids: form.scopeTargetRoleIds,
          },
        })
        .then(() => setDialogOpen(false))
        .catch(() => {});
    } else {
      addQuestion
        .mutateAsync({
          topic_id: topicId,
          question: form.question,
          category,
          scope_target_role_ids: form.scopeTargetRoleIds,
        })
        .then((created) => {
          setDialogOpen(false);
          setExpandedId(created.id);
        })
        .catch(() => {});
    }
  }

  const categoryOptions = Array.from(
    new Set((questions ?? []).map((q) => q.category?.trim()).filter((c): c is string => !!c)),
  );
  const questionGroups = groupInterviewQuestionsByCategory(questions ?? []);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Interview Questions</CardTitle>
        <div className={cn("flex items-center", ACTION_BUTTON_ROW_GAP)}>
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
            {isEditMode ? "Done" : "Edit"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {questions?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No interview questions yet — add one to start practicing.
          </p>
        )}
        {questionGroups.map((group) => (
          <div key={group.category ?? "__uncategorized"} className="flex flex-col gap-2">
            {group.category && (
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {group.category}
              </p>
            )}
            {group.questions.map((question) => {
              const allInScope = questions ?? [];
              const scopeIndex = allInScope.findIndex((q) => q.id === question.id);
              return (
                <QuestionCard
                  key={question.id}
                  question={question}
                  topics={topics}
                  index={scopeIndex}
                  total={allInScope.length}
                  isEditMode={isEditMode}
                  onMove={(direction) => moveQuestion.mutate({ id: question.id, direction })}
                  moveDisabled={moveQuestion.isPending}
                  onEdit={() => openEditDialog(question)}
                  onDelete={() => setDeleteTarget(question)}
                  scope={scope}
                  isOpen={expandedId === question.id}
                  onToggleOpen={() => toggleExpanded(question.id)}
                  expandedFollowUpId={expandedFollowUpId}
                  setExpandedFollowUpId={setExpandedFollowUpId}
                />
              );
            })}
          </div>
        ))}
      </CardContent>

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editingId ? "Edit question" : "Add question"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="question-text">Question</Label>
            <Textarea
              id="question-text"
              required
              value={form.question}
              onChange={(e) => setForm({ ...form, question: e.target.value })}
              rows={3}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="question-category">Category (optional)</Label>
            <Input
              id="question-category"
              list="interview-question-categories"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              placeholder="e.g. Behavioral, Technical"
            />
            <datalist id="interview-question-categories">
              {categoryOptions.map((option) => (
                <option key={option} value={option} />
              ))}
            </datalist>
          </div>
          {topics.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="question-topic">Related topic (optional)</Label>
              <Select
                id="question-topic"
                value={form.topic_id}
                onChange={(e) => setForm({ ...form, topic_id: e.target.value })}
              >
                <option value="">None</option>
                {topics.map((topic) => (
                  <option key={topic.id} value={topic.id}>
                    {topic.name}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <ScopeTagSelector
            id="question-scopes"
            options={scopeOptions}
            selected={form.scopeTargetRoleIds}
            onChange={(next) => setForm({ ...form, scopeTargetRoleIds: next })}
          />
          {form.scopeTargetRoleIds.length === 0 && (
            <p role="alert" className="text-sm text-destructive">
              Select at least one scope.
            </p>
          )}
          <Button
            type="submit"
            disabled={
              addQuestion.isPending || updateQuestion.isPending || form.scopeTargetRoleIds.length === 0
            }
          >
            {addQuestion.isPending || updateQuestion.isPending
              ? "Saving..."
              : editingId
                ? "Save changes"
                : "Add question"}
          </Button>
          {(addQuestion.error ?? updateQuestion.error) && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(addQuestion.error ?? updateQuestion.error)}
            </p>
          )}
        </form>
      </Dialog>

      {deleteTarget && deleteTarget.scope_target_role_ids.length > 1 ? (
        <DeleteScopeChoiceDialog
          open={deleteTarget !== null}
          onCancel={() => setDeleteTarget(null)}
          onRemoveFromScope={() => {
            deleteQuestion.mutate({ id: deleteTarget.id, deleteEverywhere: false });
            setDeleteTarget(null);
          }}
          onDeleteEverywhere={() => {
            deleteQuestion.mutate({ id: deleteTarget.id, deleteEverywhere: true });
            setDeleteTarget(null);
          }}
          itemLabel={deleteTarget.question}
          scopeLabel={scopeLabelFor(scope, targetRoles)}
          isPending={deleteQuestion.isPending}
        />
      ) : (
        <ConfirmDialog
          open={deleteTarget !== null}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => {
            if (deleteTarget) deleteQuestion.mutate({ id: deleteTarget.id, deleteEverywhere: true });
            setDeleteTarget(null);
          }}
          title="Delete question?"
          description="Remove this question, its answers, and its reference links? This can't be undone."
          isPending={deleteQuestion.isPending}
        />
      )}
    </Card>
  );
}

function QuestionCard({
  question,
  topics,
  index,
  total,
  isEditMode,
  onMove,
  moveDisabled,
  onEdit,
  onDelete,
  scope,
  isOpen,
  onToggleOpen,
  expandedFollowUpId,
  setExpandedFollowUpId,
}: {
  question: InterviewQuestion;
  topics: InterviewTopic[];
  index: number;
  total: number;
  isEditMode: boolean;
  onMove: (direction: "up" | "down") => void;
  moveDisabled: boolean;
  onEdit: () => void;
  onDelete: () => void;
  scope: string | null;
  isOpen: boolean;
  onToggleOpen: () => void;
  // Lifted to InterviewPrepPage — see its own comment for why a
  // follow-up's open/closed state isn't local to this card.
  expandedFollowUpId: string | null;
  setExpandedFollowUpId: Dispatch<SetStateAction<string | null>>;
}) {
  const updateQuestion = useUpdateInterviewQuestion(scope);
  const generateAnswer = useGenerateInterviewAnswer(scope);
  const addFollowUp = useAddFollowUpQuestion(scope);
  const moveFollowUp = useMoveFollowUpQuestion(scope);
  const deleteFollowUp = useDeleteFollowUpQuestion(scope);

  const [followUpDraft, setFollowUpDraft] = useState("");
  const [deleteFollowUpTarget, setDeleteFollowUpTarget] = useState<InterviewQuestion | null>(null);

  function addFollowUpQuestion(event: FormEvent) {
    event.preventDefault();
    if (!followUpDraft.trim()) return;
    addFollowUp.mutate(
      { parentQuestionId: question.id, body: { question: followUpDraft } },
      {
        onSuccess: (created) => {
          setFollowUpDraft("");
          setExpandedFollowUpId(created.id);
        },
      },
    );
  }

  // Readonly-by-default: the saved answer displays as plain text with an
  // Edit button; the Textarea + Save button only appear while actively
  // editing. Draft is seeded fresh each time editing starts (not kept in
  // sync reactively), same "initialize once at the moment edit opens"
  // convention every other edit form in this app already follows.
  const [isEditingAnswer, setIsEditingAnswer] = useState(false);
  const [manualAnswerDraft, setManualAnswerDraft] = useState(question.manual_answer ?? "");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkLabel, setLinkLabel] = useState("");
  // Confirm-before-delete for reference links, same standing convention
  // every other delete action in this app follows — a real user report
  // caught this list's "x" button deleting immediately with no
  // confirmation, unlike everything else here.
  const [deleteLinkIndex, setDeleteLinkIndex] = useState<number | null>(null);
  // AI-Suggested Answer starts hidden — it's the model's text, not the
  // user's own, and can be long/distracting until deliberately wanted.
  // Generating/regenerating auto-reveals it, same "show the thing you
  // just asked for" convention this app already uses elsewhere (e.g.
  // auto-expanding a newly-added item).
  const [isAiAnswerVisible, setIsAiAnswerVisible] = useState(false);

  const linkedTopic = topics.find((t) => t.id === question.topic_id);

  function startEditingAnswer() {
    setManualAnswerDraft(question.manual_answer ?? "");
    setIsEditingAnswer(true);
  }

  function saveManualAnswer() {
    updateQuestion.mutate(
      {
        id: question.id,
        body: {
          question: question.question,
          topic_id: question.topic_id,
          category: question.category,
          manual_answer: manualAnswerDraft || null,
          reference_links: question.reference_links,
          scope_target_role_ids: question.scope_target_role_ids,
        },
      },
      { onSuccess: () => setIsEditingAnswer(false) },
    );
  }

  function addLink(event: FormEvent) {
    event.preventDefault();
    if (!linkUrl.trim() || !linkLabel.trim()) return;
    const nextLinks: ReferenceLink[] = [
      ...question.reference_links,
      { url: linkUrl.trim(), label: linkLabel.trim() },
    ];
    updateQuestion.mutate({
      id: question.id,
      body: {
        question: question.question,
        topic_id: question.topic_id,
        category: question.category,
        manual_answer: question.manual_answer,
        reference_links: nextLinks,
        scope_target_role_ids: question.scope_target_role_ids,
      },
    });
    setLinkUrl("");
    setLinkLabel("");
  }

  function confirmRemoveLink() {
    if (deleteLinkIndex === null) return;
    const nextLinks = question.reference_links.filter((_, i) => i !== deleteLinkIndex);
    updateQuestion.mutate({
      id: question.id,
      body: {
        question: question.question,
        topic_id: question.topic_id,
        category: question.category,
        manual_answer: question.manual_answer,
        reference_links: nextLinks,
        scope_target_role_ids: question.scope_target_role_ids,
      },
    });
    setDeleteLinkIndex(null);
  }

  return (
    <div
      id={`interview-question-${question.id}`}
      className={cn(
        "flex flex-col gap-3 rounded-md border border-border p-4",
        index % 2 === 0 ? "bg-card" : "bg-muted",
      )}
    >
      <div
        className="flex cursor-pointer items-start justify-between gap-3"
        onClick={onToggleOpen}
      >
        <div className="flex items-start gap-2">
          {isEditMode && (
            <div onClick={(e) => e.stopPropagation()}>
              <MoveButtons
                onMoveUp={() => onMove("up")}
                onMoveDown={() => onMove("down")}
                isFirst={index === 0}
                isLast={index === total - 1}
                disabled={moveDisabled}
              />
            </div>
          )}
          <div>
            <p className="text-sm font-medium md:text-base">
              <span className="font-normal text-muted-foreground">Question: </span>
              {question.question}
            </p>
            {isOpen && linkedTopic && (
              <p className="text-xs text-muted-foreground">Related topic: {linkedTopic.name}</p>
            )}
          </div>
        </div>
        <div
          className={cn("flex shrink-0 items-center", ACTION_BUTTON_ROW_GAP)}
          onClick={(e) => e.stopPropagation()}
        >
          {isEditMode && (
            <>
              <Button variant="ghost" size="sm" onClick={onEdit}>
                <Pencil className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={onDelete}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </>
          )}
          <CollapseToggle isOpen={isOpen} onToggle={onToggleOpen} label={question.question} />
        </div>
      </div>

      {isOpen && (
      <>
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Answer:
            </p>
            {!isEditingAnswer && (
              <Button variant="ghost" size="sm" onClick={startEditingAnswer}>
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
            )}
          </div>
          {isEditingAnswer ? (
            <>
              <RichTextEditor
                defaultValue={manualAnswerDraft}
                onChange={setManualAnswerDraft}
                placeholder="Write your own answer..."
                autoFocus
              />
              <div className={cn("flex", ACTION_BUTTON_ROW_GAP)}>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={saveManualAnswer}
                  disabled={updateQuestion.isPending}
                >
                  {updateQuestion.isPending ? "Saving..." : "Save answer"}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setIsEditingAnswer(false)}>
                  Cancel
                </Button>
              </div>
            </>
          ) : question.manual_answer ? (
            <RichTextDisplay
              html={question.manual_answer}
              className="max-h-48 overflow-y-auto scrollbar-hide"
            />
          ) : (
            <p className="text-sm text-muted-foreground">No answer yet — click Edit to add one.</p>
          )}
        </div>

        <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              AI-Suggested Answer
            </p>
            <CollapseToggle
              isOpen={isAiAnswerVisible}
              onToggle={() => setIsAiAnswerVisible((v) => !v)}
              label="AI-Suggested Answer"
            />
          </div>
          {isAiAnswerVisible && (
            <>
              {question.ai_answer_status === "generated" && (
                <div className="max-h-48 overflow-y-auto whitespace-pre-line text-sm scrollbar-hide">
                  {question.ai_answer}
                </div>
              )}
              {question.ai_answer_status === "failed" && (
                <p role="alert" className="text-sm text-destructive">
                  {question.ai_answer_error ?? "Something went wrong generating an answer."}
                </p>
              )}
              {!question.ai_answer_status && (
                <p className="text-sm text-muted-foreground">No AI answer generated yet.</p>
              )}
            </>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              generateAnswer.mutate(question.id, { onSuccess: () => setIsAiAnswerVisible(true) })
            }
            disabled={generateAnswer.isPending}
            className="self-start"
          >
            {question.ai_answer_status ? (
              <RefreshCw className="h-4 w-4" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {generateAnswer.isPending
              ? "Generating..."
              : question.ai_answer_status
                ? "Regenerate"
                : "Generate"}
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Follow-up Questions
        </p>
        {question.follow_ups.length === 0 && (
          <p className="text-sm text-muted-foreground">No follow-up questions yet.</p>
        )}
        <div className="flex flex-col gap-2">
          {question.follow_ups.map((followUp, followUpIndex) => (
            <FollowUpQuestionCard
              key={followUp.id}
              followUp={followUp}
              scope={scope}
              index={followUpIndex}
              total={question.follow_ups.length}
              isEditMode={isEditMode}
              onMove={(direction) =>
                moveFollowUp.mutate({ id: followUp.id, direction, parentQuestionId: question.id })
              }
              moveDisabled={moveFollowUp.isPending}
              onDelete={() => setDeleteFollowUpTarget(followUp)}
              isOpen={expandedFollowUpId === followUp.id}
              onToggleOpen={() =>
                setExpandedFollowUpId((prev) => (prev === followUp.id ? null : followUp.id))
              }
            />
          ))}
        </div>
        <form className="flex flex-wrap items-center gap-2" onSubmit={addFollowUpQuestion}>
          <Input
            value={followUpDraft}
            onChange={(e) => setFollowUpDraft(e.target.value)}
            placeholder="Add a follow-up question..."
            className="min-w-64 flex-1"
          />
          <Button type="submit" variant="ghost" size="sm" disabled={addFollowUp.isPending}>
            <Plus className="h-4 w-4" />
            Add follow-up
          </Button>
        </form>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Reference Links
        </p>
        {question.reference_links.length > 0 && (
          <ul className="flex flex-col gap-1">
            {question.reference_links.map((link, i) => (
              <li key={`${link.url}-${i}`} className="flex items-center gap-2">
                <a
                  href={link.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
                >
                  {link.label}
                </a>
                <button
                  type="button"
                  onClick={() => setDeleteLinkIndex(i)}
                  aria-label={`Remove link "${link.label}"`}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <form className="flex flex-wrap items-center gap-2" onSubmit={addLink}>
          <Input
            value={linkLabel}
            onChange={(e) => setLinkLabel(e.target.value)}
            placeholder="Label"
            className="w-40"
          />
          <Input
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://..."
            type="url"
            className="w-64"
          />
          <Button type="submit" variant="ghost" size="sm" disabled={updateQuestion.isPending}>
            <Plus className="h-4 w-4" />
            Add link
          </Button>
        </form>
      </div>
      </>
      )}

      <ConfirmDialog
        open={deleteFollowUpTarget !== null}
        onCancel={() => setDeleteFollowUpTarget(null)}
        onConfirm={() => {
          if (deleteFollowUpTarget) {
            deleteFollowUp.mutate({ id: deleteFollowUpTarget.id, parentQuestionId: question.id });
          }
          setDeleteFollowUpTarget(null);
        }}
        title="Delete follow-up question?"
        description="Remove this follow-up question, its answers, and its reference links? This can't be undone."
        isPending={deleteFollowUp.isPending}
      />

      <ConfirmDialog
        open={deleteLinkIndex !== null}
        onCancel={() => setDeleteLinkIndex(null)}
        onConfirm={confirmRemoveLink}
        title="Remove reference link?"
        description={
          deleteLinkIndex !== null
            ? `Remove "${question.reference_links[deleteLinkIndex]?.label}"? This can't be undone.`
            : ""
        }
        isPending={updateQuestion.isPending}
      />
    </div>
  );
}

/** A follow-up question — the same InterviewQuestion shape as a
 * top-level question (its own Manual Answer, AI-Suggested Answer, and
 * Reference Links, all reused as-is), just narrower: no category, no
 * topic link, no ScopeTagSelector (a follow-up is never independently
 * scope-tagged — it's visible wherever its parent is). Deliberately a
 * separate, leaner component rather than overloading QuestionCard with
 * a "follow-up mode" branch throughout — the two have genuinely
 * different editable surfaces. */
function FollowUpQuestionCard({
  followUp,
  scope,
  index,
  total,
  isEditMode,
  onMove,
  moveDisabled,
  onDelete,
  isOpen,
  onToggleOpen,
}: {
  followUp: InterviewQuestion;
  scope: string | null;
  index: number;
  total: number;
  isEditMode: boolean;
  onMove: (direction: "up" | "down") => void;
  moveDisabled: boolean;
  onDelete: () => void;
  isOpen: boolean;
  onToggleOpen: () => void;
}) {
  const updateFollowUp = useUpdateFollowUpQuestion(scope);
  const generateAnswer = useGenerateInterviewAnswer(scope);

  const [isEditingQuestion, setIsEditingQuestion] = useState(false);
  const [questionDraft, setQuestionDraft] = useState(followUp.question);
  const [isEditingAnswer, setIsEditingAnswer] = useState(false);
  const [manualAnswerDraft, setManualAnswerDraft] = useState(followUp.manual_answer ?? "");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkLabel, setLinkLabel] = useState("");
  const [deleteLinkIndex, setDeleteLinkIndex] = useState<number | null>(null);
  const [isAiAnswerVisible, setIsAiAnswerVisible] = useState(false);

  function startEditingQuestion() {
    setQuestionDraft(followUp.question);
    setIsEditingQuestion(true);
  }

  function saveQuestionText() {
    if (!questionDraft.trim()) return;
    updateFollowUp.mutate(
      {
        id: followUp.id,
        body: {
          question: questionDraft,
          manual_answer: followUp.manual_answer,
          reference_links: followUp.reference_links,
        },
      },
      { onSuccess: () => setIsEditingQuestion(false) },
    );
  }

  function startEditingAnswer() {
    setManualAnswerDraft(followUp.manual_answer ?? "");
    setIsEditingAnswer(true);
  }

  function saveManualAnswer() {
    updateFollowUp.mutate(
      {
        id: followUp.id,
        body: {
          question: followUp.question,
          manual_answer: manualAnswerDraft || null,
          reference_links: followUp.reference_links,
        },
      },
      { onSuccess: () => setIsEditingAnswer(false) },
    );
  }

  function addLink(event: FormEvent) {
    event.preventDefault();
    if (!linkUrl.trim() || !linkLabel.trim()) return;
    const nextLinks: ReferenceLink[] = [
      ...followUp.reference_links,
      { url: linkUrl.trim(), label: linkLabel.trim() },
    ];
    updateFollowUp.mutate({
      id: followUp.id,
      body: { question: followUp.question, manual_answer: followUp.manual_answer, reference_links: nextLinks },
    });
    setLinkUrl("");
    setLinkLabel("");
  }

  function confirmRemoveLink() {
    if (deleteLinkIndex === null) return;
    const nextLinks = followUp.reference_links.filter((_, i) => i !== deleteLinkIndex);
    updateFollowUp.mutate({
      id: followUp.id,
      body: { question: followUp.question, manual_answer: followUp.manual_answer, reference_links: nextLinks },
    });
    setDeleteLinkIndex(null);
  }

  return (
    <div
      id={`interview-question-${followUp.id}`}
      className={cn(
        "flex flex-col gap-2 rounded-md border border-border p-3",
        index % 2 === 0 ? "bg-card" : "bg-muted",
      )}
    >
      <div className="flex cursor-pointer items-start justify-between gap-3" onClick={onToggleOpen}>
        <div className="flex items-start gap-2">
          {isEditMode && (
            <div onClick={(e) => e.stopPropagation()}>
              <MoveButtons
                onMoveUp={() => onMove("up")}
                onMoveDown={() => onMove("down")}
                isFirst={index === 0}
                isLast={index === total - 1}
                disabled={moveDisabled}
              />
            </div>
          )}
          <p className="text-sm font-medium md:text-base">
            <span className="font-normal text-muted-foreground">Follow-up: </span>
            {followUp.question}
          </p>
        </div>
        <div
          className={cn("flex shrink-0 items-center", ACTION_BUTTON_ROW_GAP)}
          onClick={(e) => e.stopPropagation()}
        >
          {isEditMode && (
            <>
              <Button variant="ghost" size="sm" onClick={startEditingQuestion}>
                <Pencil className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" onClick={onDelete}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </>
          )}
          <CollapseToggle isOpen={isOpen} onToggle={onToggleOpen} label={followUp.question} />
        </div>
      </div>

      {isEditingQuestion && (
        <div className="flex flex-col gap-2" onClick={(e) => e.stopPropagation()}>
          <Textarea
            value={questionDraft}
            onChange={(e) => setQuestionDraft(e.target.value)}
            rows={2}
          />
          <div className={cn("flex", ACTION_BUTTON_ROW_GAP)}>
            <Button
              variant="outline"
              size="sm"
              onClick={saveQuestionText}
              disabled={updateFollowUp.isPending}
            >
              {updateFollowUp.isPending ? "Saving..." : "Save"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setIsEditingQuestion(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {isOpen && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Answer:
              </p>
              {!isEditingAnswer && (
                <Button variant="ghost" size="sm" onClick={startEditingAnswer}>
                  <Pencil className="h-4 w-4" />
                  Edit
                </Button>
              )}
            </div>
            {isEditingAnswer ? (
              <>
                <RichTextEditor
                  defaultValue={manualAnswerDraft}
                  onChange={setManualAnswerDraft}
                  placeholder="Write your own answer..."
                  autoFocus
                />
                <div className={cn("flex", ACTION_BUTTON_ROW_GAP)}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={saveManualAnswer}
                    disabled={updateFollowUp.isPending}
                  >
                    {updateFollowUp.isPending ? "Saving..." : "Save answer"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setIsEditingAnswer(false)}>
                    Cancel
                  </Button>
                </div>
              </>
            ) : followUp.manual_answer ? (
              <RichTextDisplay
                html={followUp.manual_answer}
                className="max-h-48 overflow-y-auto scrollbar-hide"
              />
            ) : (
              <p className="text-sm text-muted-foreground">No answer yet — click Edit to add one.</p>
            )}
          </div>

          <div className="flex flex-col gap-2 rounded-md border border-border bg-background p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                AI-Suggested Answer
              </p>
              <CollapseToggle
                isOpen={isAiAnswerVisible}
                onToggle={() => setIsAiAnswerVisible((v) => !v)}
                label="AI-Suggested Answer"
              />
            </div>
            {isAiAnswerVisible && (
              <>
                {followUp.ai_answer_status === "generated" && (
                  <div className="max-h-48 overflow-y-auto whitespace-pre-line text-sm scrollbar-hide">
                    {followUp.ai_answer}
                  </div>
                )}
                {followUp.ai_answer_status === "failed" && (
                  <p role="alert" className="text-sm text-destructive">
                    {followUp.ai_answer_error ?? "Something went wrong generating an answer."}
                  </p>
                )}
                {!followUp.ai_answer_status && (
                  <p className="text-sm text-muted-foreground">No AI answer generated yet.</p>
                )}
              </>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                generateAnswer.mutate(followUp.id, { onSuccess: () => setIsAiAnswerVisible(true) })
              }
              disabled={generateAnswer.isPending}
              className="self-start"
            >
              {followUp.ai_answer_status ? (
                <RefreshCw className="h-4 w-4" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {generateAnswer.isPending
                ? "Generating..."
                : followUp.ai_answer_status
                  ? "Regenerate"
                  : "Generate"}
            </Button>
          </div>

          <div className="flex flex-col gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Reference Links
            </p>
            {followUp.reference_links.length > 0 && (
              <ul className="flex flex-col gap-1">
                {followUp.reference_links.map((link, i) => (
                  <li key={`${link.url}-${i}`} className="flex items-center gap-2">
                    <a
                      href={link.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-accent underline underline-offset-2 hover:text-accent/80"
                    >
                      {link.label}
                    </a>
                    <button
                      type="button"
                      onClick={() => setDeleteLinkIndex(i)}
                      aria-label={`Remove link "${link.label}"`}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <form className="flex flex-wrap items-center gap-2" onSubmit={addLink}>
              <Input
                value={linkLabel}
                onChange={(e) => setLinkLabel(e.target.value)}
                placeholder="Label"
                className="w-40"
              />
              <Input
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                placeholder="https://..."
                type="url"
                className="w-64"
              />
              <Button type="submit" variant="ghost" size="sm" disabled={updateFollowUp.isPending}>
                <Plus className="h-4 w-4" />
                Add link
              </Button>
            </form>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={deleteLinkIndex !== null}
        onCancel={() => setDeleteLinkIndex(null)}
        onConfirm={confirmRemoveLink}
        title="Remove reference link?"
        description={
          deleteLinkIndex !== null
            ? `Remove "${followUp.reference_links[deleteLinkIndex]?.label}"? This can't be undone.`
            : ""
        }
        isPending={updateFollowUp.isPending}
      />
    </div>
  );
}
