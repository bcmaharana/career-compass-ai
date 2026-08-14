import {
  useAddCertification,
  useCertifications,
  useClearCertifications,
  useDeleteCertification,
  useMoveCertification,
  useUpdateCertification,
} from "@/api/queries/career-profile";
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
import { Select } from "@/components/ui/select";
import { useProfileScope } from "@/features/career-profile/profile-scope";
import { ResumeIncludeToggle } from "@/features/career-profile/ResumeIncludeToggle";
import { itemAlternateClass, type SectionOrderProps } from "@/features/career-profile/section-order";
import { formatDisplayDate } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Eraser, Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

type Certification = components["schemas"]["CertificationResponse"];

interface FormState {
  name: string;
  issuing_organization: string;
  issue_date: string;
  expiration_date: string;
  credential_id: string;
  credential_url: string;
  include_in_resume: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  issuing_organization: "",
  issue_date: "",
  expiration_date: "",
  credential_id: "",
  credential_url: "",
  include_in_resume: true,
};

function toFormState(certification: Certification): FormState {
  return {
    name: certification.name,
    issuing_organization: certification.issuing_organization,
    issue_date: certification.issue_date ?? "",
    expiration_date: certification.expiration_date ?? "",
    credential_id: certification.credential_id ?? "",
    credential_url: certification.credential_url ?? "",
    include_in_resume: certification.include_in_resume,
  };
}

export function CertificationSection({
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  moveDisabled,
  cardBackground,
  resumeIncluded,
  onToggleResumeIncluded,
  resumeToggleDisabled,
}: SectionOrderProps) {
  const scope = useProfileScope();
  const { data: certifications, isLoading } = useCertifications(scope);
  const addCertification = useAddCertification(scope);
  const updateCertification = useUpdateCertification(scope);
  const deleteCertification = useDeleteCertification(scope);
  const clearCertifications = useClearCertifications(scope);
  const moveCertification = useMoveCertification(scope);
  const { data: masterCertifications } = useCertifications(null);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [isOpen, setIsOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Certification | null>(null);
  const [clearSectionOpen, setClearSectionOpen] = useState(false);

  function openAddDialog() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(certification: Certification) {
    setEditingId(certification.id);
    setForm(toFormState(certification));
    setDialogOpen(true);
  }

  function copyFromMaster(certificationId: string) {
    const source = masterCertifications?.find((c) => c.id === certificationId);
    if (source) setForm(toFormState(source));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = {
      name: form.name,
      issuing_organization: form.issuing_organization,
      issue_date: form.issue_date || null,
      expiration_date: form.expiration_date || null,
      credential_id: form.credential_id || null,
      credential_url: form.credential_url || null,
      include_in_resume: form.include_in_resume,
    };

    const mutation = editingId
      ? updateCertification.mutateAsync({ id: editingId, body })
      : addCertification.mutateAsync(body);

    mutation
      .then(() => {
        setDialogOpen(false);
        if (!editingId) setIsOpen(true);
      })
      .catch(() => {});
  }

  function toggleItemResume(certification: Certification, include: boolean) {
    updateCertification.mutate({
      id: certification.id,
      body: {
        name: certification.name,
        issuing_organization: certification.issuing_organization,
        issue_date: certification.issue_date,
        expiration_date: certification.expiration_date,
        credential_id: certification.credential_id,
        credential_url: certification.credential_url,
        include_in_resume: include,
      },
    });
  }

  const isSaving = addCertification.isPending || updateCertification.isPending;
  const saveError = addCertification.error ?? updateCertification.error;

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <CardTitle>Certifications</CardTitle>
        <div className={cn("flex items-start", ACTION_BUTTON_ROW_GAP)}>
          <ResumeIncludeToggle
            checked={resumeIncluded}
            onCheckedChange={onToggleResumeIncluded}
            disabled={resumeToggleDisabled}
            label="the Certifications section"
          />
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsEditMode((v) => !v)}>
            {isEditMode ? "Done" : "Edit"}
          </Button>
          {!!certifications?.length && (
            <Button variant="ghost" size="sm" onClick={() => setClearSectionOpen(true)}>
              <Eraser className="h-4 w-4" />
              Clear
            </Button>
          )}
          <CollapseToggle
            isOpen={isOpen}
            onToggle={() => setIsOpen(!isOpen)}
            label="Certifications"
          />
          <MoveButtons
            onMoveUp={onMoveUp}
            onMoveDown={onMoveDown}
            isFirst={isFirst}
            isLast={isLast}
            disabled={moveDisabled}
          />
        </div>
      </CardHeader>
      {isOpen && (
      <CardContent className="flex flex-col gap-3">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {certifications?.length === 0 && (
          <p className="text-sm text-muted-foreground">No certifications added yet.</p>
        )}
        {certifications?.map((certification, index) => (
          <div
            key={certification.id}
            className={cn(
              "flex items-start justify-between gap-4 rounded-md border border-border p-4",
              itemAlternateClass(cardBackground, index),
            )}
          >
            {isEditMode && (
              <MoveButtons
                onMoveUp={() => moveCertification.mutate({ id: certification.id, direction: "up" })}
                onMoveDown={() =>
                  moveCertification.mutate({ id: certification.id, direction: "down" })
                }
                isFirst={index === 0}
                isLast={index === certifications.length - 1}
                disabled={moveCertification.isPending}
              />
            )}
            <div className="flex-1">
              <p className="text-sm font-medium md:text-base">{certification.name}</p>
              <p className="text-sm text-muted-foreground">
                {certification.issuing_organization}
              </p>
              {certification.expiration_date && (
                <p className="text-xs font-bold italic text-accent">
                  Expires {formatDisplayDate(certification.expiration_date)}
                </p>
              )}
            </div>
            <div className={cn("flex shrink-0", ACTION_BUTTON_ROW_GAP)}>
              <ResumeIncludeToggle
                checked={certification.include_in_resume}
                onCheckedChange={(checked) => toggleItemResume(certification, checked)}
                disabled={updateCertification.isPending}
                label={`the "${certification.name}" certification entry`}
              />
              {isEditMode && (
                <>
                  <Button variant="ghost" size="sm" onClick={() => openEditDialog(certification)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(certification)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </>
              )}
            </div>
          </div>
        ))}
      </CardContent>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editingId ? "Edit certification" : "Add certification"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          {!editingId && scope !== null && !!masterCertifications?.length && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cert-copy-from-master">Copy from Master (optional)</Label>
              <Select id="cert-copy-from-master" value="" onChange={(e) => copyFromMaster(e.target.value)}>
                <option value="">Start blank</option>
                {masterCertifications.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cert-name">Name</Label>
            <Input
              id="cert-name"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cert-org">Issuing organization</Label>
            <Input
              id="cert-org"
              required
              value={form.issuing_organization}
              onChange={(e) => setForm({ ...form, issuing_organization: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cert-issue">Issue date</Label>
              <Input
                id="cert-issue"
                type="date"
                value={form.issue_date}
                onChange={(e) => setForm({ ...form, issue_date: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cert-expiration">Expiration date</Label>
              <Input
                id="cert-expiration"
                type="date"
                value={form.expiration_date}
                onChange={(e) => setForm({ ...form, expiration_date: e.target.value })}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cert-credential-id">Credential ID</Label>
            <Input
              id="cert-credential-id"
              value={form.credential_id}
              onChange={(e) => setForm({ ...form, credential_id: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cert-url">Credential URL</Label>
            <Input
              id="cert-url"
              type="url"
              value={form.credential_url}
              onChange={(e) => setForm({ ...form, credential_url: e.target.value })}
            />
          </div>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add certification"}
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
          if (deleteTarget) deleteCertification.mutate(deleteTarget.id);
          setDeleteTarget(null);
        }}
        title="Delete certification?"
        description={deleteTarget ? `Remove "${deleteTarget.name}"? This can't be undone.` : ""}
        isPending={deleteCertification.isPending}
      />

      <ConfirmDialog
        open={clearSectionOpen}
        onCancel={() => setClearSectionOpen(false)}
        onConfirm={() => {
          clearCertifications.mutate();
          setClearSectionOpen(false);
        }}
        title="Clear Certifications?"
        description="Remove every certification from your profile? This can't be undone."
        isPending={clearCertifications.isPending}
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
      />
    </Card>
  );
}
