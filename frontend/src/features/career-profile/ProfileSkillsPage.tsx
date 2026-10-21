import { useProfileSkills } from "@/api/queries/profile-skills";
import {
  useAddProfileSkill,
  useProfileSkillFileUrl,
  useDeleteProfileSkill,
  useDeleteProfileSkillFile,
  useMoveProfileSkill,
  useRevokeProfileSkillShare,
  useShareProfileSkill,
  useUpdateProfileSkill,
  useUploadProfileSkillFile,
} from "@/api/queries/profile-skills";
import type { ProfileSkill, ProfileSkillRequest } from "@/api/queries/profile-skills";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MoveButtons } from "@/components/ui/move-buttons";
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";
import { formatDisplayDate } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { BadgeCheck, Copy, ExternalLink, FileBadge, Pencil, Plus, Share2, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import type { ReactNode } from "react";

interface ProfileSkillForm {
  name: string;
  issuing_organization: string;
  issue_date: string;
  expiration_date: string;
  credential_id: string;
  credential_url: string;
  badge_url: string;
  include_in_resume: boolean;
}

const EMPTY_FORM: ProfileSkillForm = {
  name: "",
  issuing_organization: "",
  issue_date: "",
  expiration_date: "",
  credential_id: "",
  credential_url: "",
  badge_url: "",
  include_in_resume: true,
};

function getForm(skill: ProfileSkill): ProfileSkillForm {
  return {
    name: skill.name,
    issuing_organization: skill.issuing_organization,
    issue_date: skill.issue_date ?? "",
    expiration_date: skill.expiration_date ?? "",
    credential_id: skill.credential_id ?? "",
    credential_url: skill.credential_url ?? "",
    badge_url: skill.badge_url ?? "",
    include_in_resume: skill.include_in_resume,
  };
}

function requestFromForm(form: ProfileSkillForm): ProfileSkillRequest {
  return {
    name: form.name.trim(),
    issuing_organization: form.issuing_organization.trim(),
    issue_date: form.issue_date || null,
    expiration_date: form.expiration_date || null,
    credential_id: form.credential_id.trim() || null,
    credential_url: form.credential_url.trim() || null,
    badge_url: form.badge_url.trim() || null,
    include_in_resume: form.include_in_resume,
  };
}

export function ProfileSkillsPage() {
  const { data: rawProfileSkills, isLoading, isError, error } = useProfileSkills();
  const addProfileSkill = useAddProfileSkill();
  const updateProfileSkill = useUpdateProfileSkill();
  const deleteProfileSkill = useDeleteProfileSkill();
  const moveProfileSkill = useMoveProfileSkill();
  const uploadFile = useUploadProfileSkillFile();
  const deleteFile = useDeleteProfileSkillFile();
  const fileUrl = useProfileSkillFileUrl();
  const shareProfileSkill = useShareProfileSkill();
  const revokeShare = useRevokeProfileSkillShare();
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<ProfileSkillForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ProfileSkill | null>(null);
  const [shareOverrides, setShareOverrides] = useState<Record<string, string | null>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const { copy, copied } = useCopyToClipboard();
  const skills = rawProfileSkills as ProfileSkill[] | undefined;

  function openAdd() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
  }

  function openEdit(skill: ProfileSkill) {
    setEditingId(skill.id);
    setForm(getForm(skill));
    setFormOpen(true);
  }

  async function saveProfileSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionError(null);
    const body = requestFromForm(form);
    try {
      if (editingId) await updateProfileSkill.mutateAsync({ id: editingId, body });
      else await addProfileSkill.mutateAsync(body);
      setFormOpen(false);
    } catch (saveError) {
      setActionError(getErrorMessage(saveError));
    }
  }

  async function share(id: string) {
    setActionError(null);
    try {
      const { share_key: shareKey } = await shareProfileSkill.mutateAsync(id);
      setShareOverrides((previous) => ({ ...previous, [id]: shareKey }));
    } catch (shareError) {
      setActionError(getErrorMessage(shareError));
    }
  }

  async function revoke(id: string) {
    setActionError(null);
    try {
      await revokeShare.mutateAsync(id);
      setShareOverrides((previous) => ({ ...previous, [id]: null }));
    } catch (shareError) {
      setActionError(getErrorMessage(shareError));
    }
  }

  async function copyShareLink(shareKey: string) {
    const url = `${window.location.origin}/skill/${shareKey}`;
    setActionError(null);
    try {
      await copy(url);
    } catch (copyError) {
      setActionError(getErrorMessage(copyError));
    }
  }

  async function openFile(id: string, kind: "skill" | "badge") {
    setActionError(null);
    const preview = window.open("about:blank", "_blank");
    if (!preview) {
      setActionError("Allow pop-ups to view this file.");
      return;
    }
    preview.opener = null;
    try {
      const { url } = await fileUrl.mutateAsync({ id, kind });
      preview.location.href = url;
    } catch (fileError) {
      preview.close();
      setActionError(getErrorMessage(fileError));
    }
  }

  async function upload(id: string, kind: "skill" | "badge", file?: File) {
    if (!file) return;
    setActionError(null);
    if (file.size > 10 * 1024 * 1024) {
      setActionError("Files must be no larger than 10 MB.");
      return;
    }
    try {
      await uploadFile.mutateAsync({ id, kind, file });
    } catch (uploadError) {
      setActionError(getErrorMessage(uploadError));
    }
  }

  async function removeFile(id: string, kind: "skill" | "badge") {
    setActionError(null);
    try {
      await deleteFile.mutateAsync({ id, kind });
    } catch (removeError) {
      setActionError(getErrorMessage(removeError));
    }
  }

  const isSaving = addProfileSkill.isPending || updateProfileSkill.isPending;
  const sharedErrors = [
    uploadFile.error,
    deleteFile.error,
    fileUrl.error,
    shareProfileSkill.error,
    revokeShare.error,
    deleteProfileSkill.error,
    moveProfileSkill.error,
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold">Skills</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Keep skills in one place, attach proof and badges, and share each skill
            with its own private-by-default public link.
          </p>
        </div>
        <Button onClick={openAdd}>
          <Plus className="h-4 w-4" />
          Add skill
        </Button>
      </div>

      {actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}
      {sharedErrors.some(Boolean) && (
        <p role="alert" className="text-sm text-destructive">
          {getErrorMessage(sharedErrors.find(Boolean))}
        </p>
      )}
      {isLoading && <p className="text-sm text-muted-foreground">Loading skills...</p>}
      {isError && (
        <p role="alert" className="text-sm text-destructive">
          {getErrorMessage(error)}
        </p>
      )}
      {!isLoading && !isError && skills?.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center">
            <BadgeCheck className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No skills added yet.</p>
          </CardContent>
        </Card>
      )}
      {skills?.map((skill, index) => {
        const shareKey =
          shareOverrides[skill.id] === undefined
            ? skill.share_key
            : shareOverrides[skill.id];
        const isShared = !!shareKey;
        return (
          <Card key={skill.id}>
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <FileBadge className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                <div className="min-w-0">
                  <CardTitle>{skill.name}</CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {skill.issuing_organization}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    {skill.issue_date && (
                      <span>Issued {formatDisplayDate(skill.issue_date)}</span>
                    )}
                    {skill.expiration_date && (
                      <span>Expires {formatDisplayDate(skill.expiration_date)}</span>
                    )}
                    {skill.credential_id && <span>ID: {skill.credential_id}</span>}
                  </div>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <MoveButtons
                  onMoveUp={() => moveProfileSkill.mutate({ id: skill.id, direction: "up" })}
                  onMoveDown={() => moveProfileSkill.mutate({ id: skill.id, direction: "down" })}
                  isFirst={index === 0}
                  isLast={index === skills.length - 1}
                  disabled={moveProfileSkill.isPending}
                  label={`${skill.name} skill`}
                />
                <Button variant="ghost" size="sm" onClick={() => openEdit(skill)} aria-label={`Edit ${skill.name}`}>
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(skill)} aria-label={`Delete ${skill.name}`}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {skill.credential_url && (
                <a
                  className="inline-flex items-center gap-1 text-sm text-primary underline"
                  href={skill.credential_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Verify credential <ExternalLink className="h-3 w-3" />
                </a>
              )}
              {skill.skill_file_name ? (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span>Skill file: {skill.skill_file_name}</span>
                  <Button variant="outline" size="sm" onClick={() => openFile(skill.id, "skill")}>
                    View
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => void removeFile(skill.id, "skill")}>
                    Remove
                  </Button>
                </div>
              ) : null}
              <div className="flex flex-wrap items-center gap-2">
                <Label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-muted">
                  <input
                    className="sr-only"
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                    onChange={(event) => {
                      void upload(skill.id, "skill", event.currentTarget.files?.[0]);
                      event.currentTarget.value = "";
                    }}
                  />
                  {skill.skill_file_name ? "Replace skill file" : "Add skill file"}
                </Label>
                {skill.badge_image_name ? (
                  <>
                    <span className="text-sm text-muted-foreground">
                      Badge: {skill.badge_image_name}
                    </span>
                    <Button variant="outline" size="sm" onClick={() => openFile(skill.id, "badge")}>
                      View badge
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void removeFile(skill.id, "badge")}>
                      Remove badge
                    </Button>
                  </>
                ) : (
                  <Label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border px-3 py-2 text-sm hover:bg-muted">
                    <input
                      className="sr-only"
                      type="file"
                      accept=".jpg,.jpeg,.png,image/jpeg,image/png"
                      onChange={(event) => {
                        void upload(skill.id, "badge", event.currentTarget.files?.[0]);
                        event.currentTarget.value = "";
                      }}
                    />
                    Add badge image
                  </Label>
                )}
                {skill.badge_url && (
                  <a className="text-sm text-primary underline" href={skill.badge_url} target="_blank" rel="noreferrer">
                    Badge link
                  </a>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
                {isShared ? (
                  <>
                    <span className="text-sm text-green-700">Public link is active</span>
                    <Button variant="outline" size="sm" onClick={() => void copyShareLink(shareKey!)}>
                      <Copy className="h-3.5 w-3.5" />
                      {copied ? "Copied" : "Copy link"}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void revoke(skill.id)}>
                      Stop sharing
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={shareProfileSkill.isPending}
                    onClick={() => void share(skill.id)}
                  >
                    <Share2 className="h-3.5 w-3.5" />
                    Create public link
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        );
      })}

      <Dialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editingId ? "Edit skill" : "Add skill"}
      >
        <form className="flex flex-col gap-4" onSubmit={(event) => void saveProfileSkill(event)}>
          <Field label="Skill name" required>
            <Input
              required
              maxLength={255}
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </Field>
          <Field label="Issuing organization" required>
            <Input
              required
              maxLength={255}
              value={form.issuing_organization}
              onChange={(event) => setForm({ ...form, issuing_organization: event.target.value })}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Issue date">
              <Input
                type="date"
                value={form.issue_date}
                onChange={(event) => setForm({ ...form, issue_date: event.target.value })}
              />
            </Field>
            <Field label="Expiration date">
              <Input
                type="date"
                value={form.expiration_date}
                onChange={(event) => setForm({ ...form, expiration_date: event.target.value })}
              />
            </Field>
          </div>
          <Field label="Credential ID">
            <Input
              maxLength={255}
              value={form.credential_id}
              onChange={(event) => setForm({ ...form, credential_id: event.target.value })}
            />
          </Field>
          <Field label="Credential verification URL">
            <Input
              type="url"
              maxLength={2048}
              value={form.credential_url}
              onChange={(event) => setForm({ ...form, credential_url: event.target.value })}
            />
          </Field>
          <Field label="Badge URL (optional)">
            <Input
              type="url"
              maxLength={2048}
              value={form.badge_url}
              onChange={(event) => setForm({ ...form, badge_url: event.target.value })}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.include_in_resume}
              onChange={(event) => setForm({ ...form, include_in_resume: event.target.checked })}
            />
            Include in resume
          </label>
          {actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add skill"}
          </Button>
        </form>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            deleteProfileSkill.mutate(deleteTarget.id, {
              onSuccess: () => setDeleteTarget(null),
            });
          }
        }}
        title="Delete skill?"
        description={
          deleteTarget
            ? `Remove "${deleteTarget.name}" from your skill library? This can't be undone.`
            : ""
        }
        isPending={deleteProfileSkill.isPending}
        confirmLabel="Delete"
        confirmPendingLabel="Deleting..."
      />
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}{required ? " *" : ""}</Label>
      {children}
    </div>
  );
}
