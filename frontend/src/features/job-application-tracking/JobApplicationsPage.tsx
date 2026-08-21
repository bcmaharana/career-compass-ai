import { useTargetRoles } from "@/api/queries/career-profile";
import {
  useCreateInterviewRound,
  useCreateJobApplication,
  useDeleteInterviewRound,
  useDeleteJobApplication,
  useJobApplications,
  useMoveInterviewRound,
  useUnlinkJobApplicationSession,
  useUpdateInterviewRound,
  useUpdateJobApplication,
} from "@/api/queries/job-application-tracking";
import { useRecruiterContacts } from "@/api/queries/recruiter-contacts";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { formatDisplayDate } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { ChevronDown, ChevronUp, ExternalLink, Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

type JobApplication = components["schemas"]["JobApplicationResponse"];
type InterviewRound = components["schemas"]["InterviewRoundResponse"];
//: JobApplicationResponse.status is a plain string (the response schema
//: was left loose), but the create/update request schemas tightened
//: `status` to this literal union as part of the 2026-08-21 tech-debt
//: pass — FormState needs the stricter request-side type since it's
//: what actually gets sent back on submit.
type JobApplicationStatusValue = components["schemas"]["JobApplicationRequest"]["status"];

const STATUS_LABELS: Record<string, string> = {
  considering: "Considering",
  applied: "Applied",
  phone_screen: "Phone Screen",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  didnt_hear_back: "Didn't Hear Back",
  other: "Other",
};
const TERMINAL_STATUSES = new Set(["offer", "rejected", "withdrawn", "didnt_hear_back"]);

interface FormState {
  company: string;
  role_title: string;
  status: JobApplicationStatusValue;
  target_role_id: string;
  applied_at: string;
  notes: string;
  recruiter_id: string;
}

const EMPTY_FORM: FormState = {
  company: "",
  role_title: "",
  status: "considering",
  target_role_id: "",
  applied_at: "",
  notes: "",
  recruiter_id: "",
};

function toFormState(app: JobApplication): FormState {
  return {
    company: app.company,
    role_title: app.role_title,
    // app.status is DB-CHECK-constrained to this same set of values
    // server-side (see backend/app/domain/job_application_tracking/entities.py)
    // even though the response schema types it as a plain string.
    status: app.status as JobApplicationStatusValue,
    target_role_id: app.target_role_id ?? "",
    applied_at: app.applied_at ?? "",
    notes: app.notes ?? "",
    recruiter_id: app.recruiter_id ?? "",
  };
}

/**
 * Flat, user-scoped job application pipeline — same "not tied to a
 * career profile" shape as Learning Intelligence. Applications created
 * here manually are independent of the JD Tailoring auto-create path
 * (which already works from Opportunity Intelligence); both land in
 * this same list.
 */
export function JobApplicationsPage() {
  const { data: applications, isLoading } = useJobApplications();
  const { data: targetRoles } = useTargetRoles();
  const { data: recruiters } = useRecruiterContacts();
  const createApplication = useCreateJobApplication();
  const updateApplication = useUpdateJobApplication();
  const deleteApplication = useDeleteJobApplication();
  const unlinkSession = useUnlinkJobApplicationSession();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [deleteTarget, setDeleteTarget] = useState<JobApplication | null>(null);
  const [unlinkTarget, setUnlinkTarget] = useState<JobApplication | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  function openAddDialog() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(app: JobApplication) {
    setEditingId(app.id);
    setForm(toFormState(app));
    setDialogOpen(true);
  }

  function toggleExpanded(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (editingId) {
      updateApplication
        .mutateAsync({
          id: editingId,
          body: {
            company: form.company,
            role_title: form.role_title,
            status: form.status,
            target_role_id: form.target_role_id || null,
            applied_at: form.applied_at || null,
            notes: form.notes || null,
            recruiter_id: form.recruiter_id || null,
          },
        })
        .then(() => setDialogOpen(false))
        .catch(() => {});
    } else {
      createApplication
        .mutateAsync({
          company: form.company,
          role_title: form.role_title,
          status: form.status,
          target_role_id: form.target_role_id || null,
          applied_at: form.applied_at || null,
          notes: form.notes || null,
          recruiter_id: form.recruiter_id || null,
        })
        .then(() => setDialogOpen(false))
        .catch(() => {});
    }
  }

  const isSaving = createApplication.isPending || updateApplication.isPending;
  const saveError = createApplication.error ?? updateApplication.error;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <CardTitle>Job Applications</CardTitle>
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-3.5 w-3.5" />
            Add
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
          {applications?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No applications tracked yet — add one here, or start a JD Tailoring session from a
              Job Listing to have one created automatically.
            </p>
          )}
          {applications?.map((app) => {
            const isExpanded = expandedIds.has(app.id);
            const recruiter = recruiters?.find((r) => r.id === app.recruiter_id);
            const targetRole = targetRoles?.find((r) => r.id === app.target_role_id);
            return (
              <div key={app.id} className="rounded-md border border-border px-4 py-2">
                <div className="flex items-start justify-between gap-4">
                  <button
                    type="button"
                    onClick={() => toggleExpanded(app.id)}
                    className="flex-1 text-left"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium">{app.role_title}</p>
                      <Badge variant={TERMINAL_STATUSES.has(app.status) ? "default" : "accent"}>
                        {STATUS_LABELS[app.status] ?? app.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{app.company}</p>
                    <p className="text-xs text-muted-foreground">
                      {[
                        targetRole ? `Target role: ${targetRole.role_name}` : null,
                        recruiter ? `Recruiter: ${recruiter.name}` : null,
                        app.interview_rounds.length > 0
                          ? `${app.interview_rounds.length} interview round${app.interview_rounds.length === 1 ? "" : "s"}`
                          : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </button>
                  <div className={`flex shrink-0 items-center ${ACTION_BUTTON_ROW_GAP}`}>
                    {app.source_redirect_url && (
                      <a
                        href={app.source_redirect_url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center p-1 text-muted-foreground hover:text-accent"
                        aria-label="View original posting"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => toggleExpanded(app.id)}
                      aria-label={isExpanded ? "Hide interview rounds" : "Show interview rounds"}
                    >
                      {isExpanded ? (
                        <ChevronUp className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => openEditDialog(app)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => setDeleteTarget(app)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-3 flex flex-col gap-3 border-t border-border pt-3">
                    {app.jd_tailoring_session_id && (
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-muted-foreground">
                          Linked to a JD Tailoring session.
                        </p>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setUnlinkTarget(app)}
                          disabled={unlinkSession.isPending}
                        >
                          Unlink
                        </Button>
                      </div>
                    )}
                    {app.notes && <p className="text-sm">{app.notes}</p>}
                    <InterviewRoundList applicationId={app.id} rounds={app.interview_rounds} />
                  </div>
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editingId ? "Edit application" : "Add application"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-company">Company</Label>
            <Input
              id="ja-company"
              required
              value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-role-title">Role title</Label>
            <Input
              id="ja-role-title"
              required
              value={form.role_title}
              onChange={(e) => setForm({ ...form, role_title: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-status">Status</Label>
            <Select
              id="ja-status"
              value={form.status}
              onChange={(e) =>
                setForm({ ...form, status: e.target.value as JobApplicationStatusValue })
              }
            >
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-target-role">Target role (optional)</Label>
            <Select
              id="ja-target-role"
              value={form.target_role_id}
              onChange={(e) => setForm({ ...form, target_role_id: e.target.value })}
            >
              <option value="">None</option>
              {targetRoles?.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.role_name}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-recruiter">Recruiter (optional)</Label>
            <Select
              id="ja-recruiter"
              value={form.recruiter_id}
              onChange={(e) => setForm({ ...form, recruiter_id: e.target.value })}
            >
              <option value="">None</option>
              {recruiters?.map((recruiter) => (
                <option key={recruiter.id} value={recruiter.id}>
                  {recruiter.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-applied-at">Applied on (optional)</Label>
            <Input
              id="ja-applied-at"
              type="date"
              value={form.applied_at}
              onChange={(e) => setForm({ ...form, applied_at: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ja-notes">Notes</Label>
            <Textarea
              id="ja-notes"
              rows={3}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </div>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add application"}
          </Button>
          {saveError && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(saveError)}
            </p>
          )}
        </form>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) deleteApplication.mutate(deleteTarget.id);
          setDeleteTarget(null);
        }}
        title="Delete this application?"
        description={
          deleteTarget
            ? `Remove "${deleteTarget.role_title}" at ${deleteTarget.company}? This can't be undone.`
            : ""
        }
        isPending={deleteApplication.isPending}
      />

      <ConfirmDialog
        open={unlinkTarget !== null}
        onCancel={() => setUnlinkTarget(null)}
        onConfirm={() => {
          if (unlinkTarget) unlinkSession.mutate(unlinkTarget.id);
          setUnlinkTarget(null);
        }}
        title="Unlink from JD Tailoring session?"
        description="The application stays tracked with its current status — only the link to the JD Tailoring conversation is removed. The session itself is unaffected."
        confirmLabel="Unlink"
        confirmPendingLabel="Unlinking..."
        isPending={unlinkSession.isPending}
      />
    </div>
  );
}

function InterviewRoundList({
  applicationId,
  rounds,
}: {
  applicationId: string;
  rounds: InterviewRound[];
}) {
  const createRound = useCreateInterviewRound();
  const updateRound = useUpdateInterviewRound();
  const deleteRound = useDeleteInterviewRound();
  const moveRound = useMoveInterviewRound();

  const [formOpen, setFormOpen] = useState(false);
  const [editingRoundId, setEditingRoundId] = useState<string | null>(null);
  const [roundForm, setRoundForm] = useState({
    stage_label: "",
    round_date: "",
    interviewer_name: "",
    interviewer_title: "",
    notes: "",
  });
  const [deleteRoundTarget, setDeleteRoundTarget] = useState<InterviewRound | null>(null);

  function openAddRound() {
    setEditingRoundId(null);
    setRoundForm({
      stage_label: "",
      round_date: "",
      interviewer_name: "",
      interviewer_title: "",
      notes: "",
    });
    setFormOpen(true);
  }

  function openEditRound(round: InterviewRound) {
    setEditingRoundId(round.id);
    setRoundForm({
      stage_label: round.stage_label,
      round_date: round.round_date ?? "",
      interviewer_name: round.interviewer_name ?? "",
      interviewer_title: round.interviewer_title ?? "",
      notes: round.notes ?? "",
    });
    setFormOpen(true);
  }

  function handleRoundSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = {
      stage_label: roundForm.stage_label,
      round_date: roundForm.round_date || null,
      interviewer_name: roundForm.interviewer_name || null,
      interviewer_title: roundForm.interviewer_title || null,
      notes: roundForm.notes || null,
    };
    const mutation = editingRoundId
      ? updateRound.mutateAsync({ id: editingRoundId, body })
      : createRound.mutateAsync({ applicationId, body });
    mutation.then(() => setFormOpen(false)).catch(() => {});
  }

  const isSaving = createRound.isPending || updateRound.isPending;
  const saveError = createRound.error ?? updateRound.error;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase text-muted-foreground">Interview Rounds</p>
        <Button variant="ghost" size="sm" onClick={openAddRound}>
          <Plus className="h-3.5 w-3.5" />
          Add round
        </Button>
      </div>
      {rounds.length === 0 && (
        <p className="text-sm text-muted-foreground">No interview rounds logged yet.</p>
      )}
      {rounds.map((round, index) => (
        <div
          key={round.id}
          className="flex items-start justify-between gap-3 rounded-md border border-border px-3 py-2"
        >
          <MoveButtons
            onMoveUp={() => moveRound.mutate({ id: round.id, direction: "up" })}
            onMoveDown={() => moveRound.mutate({ id: round.id, direction: "down" })}
            isFirst={index === 0}
            isLast={index === rounds.length - 1}
            disabled={moveRound.isPending}
            className="h-7 w-7 p-0"
          />
          <div className="flex-1">
            <p className="text-sm font-medium">{round.stage_label}</p>
            <p className="text-xs text-muted-foreground">
              {[
                round.round_date ? formatDisplayDate(round.round_date) : "Date TBD",
                round.interviewer_name,
                round.interviewer_title,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
            {round.notes && <p className="mt-1 text-sm">{round.notes}</p>}
          </div>
          <div className={`flex shrink-0 ${ACTION_BUTTON_ROW_GAP}`}>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => openEditRound(round)}
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setDeleteRoundTarget(round)}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      ))}

      <Dialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingRoundId ? "Edit interview round" : "Add interview round"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleRoundSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-stage-label">Stage / round label</Label>
            <Input
              id="ir-stage-label"
              required
              placeholder="e.g. Phone Screen, Onsite Round 2"
              value={roundForm.stage_label}
              onChange={(e) => setRoundForm({ ...roundForm, stage_label: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-round-date">Date (optional — leave blank if TBD)</Label>
            <Input
              id="ir-round-date"
              type="date"
              value={roundForm.round_date}
              onChange={(e) => setRoundForm({ ...roundForm, round_date: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-interviewer-name">Interviewer name</Label>
            <Input
              id="ir-interviewer-name"
              value={roundForm.interviewer_name}
              onChange={(e) => setRoundForm({ ...roundForm, interviewer_name: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-interviewer-title">Interviewer title</Label>
            <Input
              id="ir-interviewer-title"
              value={roundForm.interviewer_title}
              onChange={(e) => setRoundForm({ ...roundForm, interviewer_title: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-notes">Notes</Label>
            <Textarea
              id="ir-notes"
              rows={3}
              value={roundForm.notes}
              onChange={(e) => setRoundForm({ ...roundForm, notes: e.target.value })}
            />
          </div>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingRoundId ? "Save changes" : "Add round"}
          </Button>
          {saveError && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(saveError)}
            </p>
          )}
        </form>
      </Dialog>

      <ConfirmDialog
        open={deleteRoundTarget !== null}
        onCancel={() => setDeleteRoundTarget(null)}
        onConfirm={() => {
          if (deleteRoundTarget) deleteRound.mutate(deleteRoundTarget.id);
          setDeleteRoundTarget(null);
        }}
        title="Delete this interview round?"
        description={
          deleteRoundTarget ? `Remove "${deleteRoundTarget.stage_label}"? This can't be undone.` : ""
        }
        isPending={deleteRound.isPending}
      />
    </div>
  );
}
