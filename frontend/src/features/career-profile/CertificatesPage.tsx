import { useCertifications, useMoveCertification } from "@/api/queries/career-profile";
import {
  useAddCertificate,
  useCertificateFileUrl,
  useDeleteCertificate,
  useDeleteCertificateFile,
  useRevokeCertificateShare,
  useShareCertificate,
  useUpdateCertificate,
  useUploadCertificateFile,
} from "@/api/queries/certificates";
import type { Certificate, CertificateRequest } from "@/api/queries/certificates";
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

interface CertificateForm {
  name: string;
  issuing_organization: string;
  issue_date: string;
  expiration_date: string;
  credential_id: string;
  credential_url: string;
  badge_url: string;
  include_in_resume: boolean;
}

const EMPTY_FORM: CertificateForm = {
  name: "",
  issuing_organization: "",
  issue_date: "",
  expiration_date: "",
  credential_id: "",
  credential_url: "",
  badge_url: "",
  include_in_resume: true,
};

function getForm(certificate: Certificate): CertificateForm {
  return {
    name: certificate.name,
    issuing_organization: certificate.issuing_organization,
    issue_date: certificate.issue_date ?? "",
    expiration_date: certificate.expiration_date ?? "",
    credential_id: certificate.credential_id ?? "",
    credential_url: certificate.credential_url ?? "",
    badge_url: certificate.badge_url ?? "",
    include_in_resume: certificate.include_in_resume,
  };
}

function requestFromForm(form: CertificateForm): CertificateRequest {
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

export function CertificatesPage() {
  const { data: rawCertificates, isLoading, isError, error } = useCertifications(null);
  const addCertificate = useAddCertificate();
  const updateCertificate = useUpdateCertificate();
  const deleteCertificate = useDeleteCertificate();
  const uploadFile = useUploadCertificateFile();
  const deleteFile = useDeleteCertificateFile();
  const fileUrl = useCertificateFileUrl();
  const shareCertificate = useShareCertificate();
  const revokeShare = useRevokeCertificateShare();
  const moveCertificate = useMoveCertification(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<CertificateForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Certificate | null>(null);
  const [shareOverrides, setShareOverrides] = useState<Record<string, string | null>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const { copy, copied } = useCopyToClipboard();
  const certificates = rawCertificates as Certificate[] | undefined;

  function openAdd() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
  }

  function openEdit(certificate: Certificate) {
    setEditingId(certificate.id);
    setForm(getForm(certificate));
    setFormOpen(true);
  }

  async function saveCertificate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActionError(null);
    const body = requestFromForm(form);
    try {
      if (editingId) await updateCertificate.mutateAsync({ id: editingId, body });
      else await addCertificate.mutateAsync(body);
      setFormOpen(false);
    } catch (saveError) {
      setActionError(getErrorMessage(saveError));
    }
  }

  async function share(id: string) {
    setActionError(null);
    try {
      const { share_key: shareKey } = await shareCertificate.mutateAsync(id);
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
    const url = `${window.location.origin}/certificate/${shareKey}`;
    setActionError(null);
    try {
      await copy(url);
    } catch (copyError) {
      setActionError(getErrorMessage(copyError));
    }
  }

  async function openFile(id: string, kind: "certificate" | "badge") {
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

  async function upload(id: string, kind: "certificate" | "badge", file?: File) {
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

  async function removeFile(id: string, kind: "certificate" | "badge") {
    setActionError(null);
    try {
      await deleteFile.mutateAsync({ id, kind });
    } catch (removeError) {
      setActionError(getErrorMessage(removeError));
    }
  }

  const isSaving = addCertificate.isPending || updateCertificate.isPending;
  const sharedErrors = [
    uploadFile.error,
    deleteFile.error,
    fileUrl.error,
    shareCertificate.error,
    revokeShare.error,
    deleteCertificate.error,
    moveCertificate.error,
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold">Certificates</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Keep certificates in one place, attach proof and badges, and share each certificate
            with its own private-by-default public link.
          </p>
        </div>
        <Button onClick={openAdd}>
          <Plus className="h-4 w-4" />
          Add certificate
        </Button>
      </div>

      {actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}
      {sharedErrors.some(Boolean) && (
        <p role="alert" className="text-sm text-destructive">
          {getErrorMessage(sharedErrors.find(Boolean))}
        </p>
      )}
      {isLoading && <p className="text-sm text-muted-foreground">Loading certificates...</p>}
      {isError && (
        <p role="alert" className="text-sm text-destructive">
          {getErrorMessage(error)}
        </p>
      )}
      {!isLoading && !isError && certificates?.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center">
            <BadgeCheck className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">No certificates added yet.</p>
          </CardContent>
        </Card>
      )}
      {certificates?.map((certificate, index) => {
        const shareKey =
          shareOverrides[certificate.id] === undefined
            ? certificate.share_key
            : shareOverrides[certificate.id];
        const isShared = !!shareKey;
        return (
          <Card key={certificate.id}>
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <FileBadge className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                <div className="min-w-0">
                  <CardTitle>{certificate.name}</CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {certificate.issuing_organization}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    {certificate.issue_date && (
                      <span>Issued {formatDisplayDate(certificate.issue_date)}</span>
                    )}
                    {certificate.expiration_date && (
                      <span>Expires {formatDisplayDate(certificate.expiration_date)}</span>
                    )}
                    {certificate.credential_id && <span>ID: {certificate.credential_id}</span>}
                  </div>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <MoveButtons
                  onMoveUp={() => moveCertificate.mutate({ id: certificate.id, direction: "up" })}
                  onMoveDown={() => moveCertificate.mutate({ id: certificate.id, direction: "down" })}
                  isFirst={index === 0}
                  isLast={index === certificates.length - 1}
                  disabled={moveCertificate.isPending}
                  label={`${certificate.name} certificate`}
                />
                <Button variant="ghost" size="sm" onClick={() => openEdit(certificate)} aria-label={`Edit ${certificate.name}`}>
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(certificate)} aria-label={`Delete ${certificate.name}`}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {certificate.credential_url && (
                <a
                  className="inline-flex items-center gap-1 text-sm text-primary underline"
                  href={certificate.credential_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Verify credential <ExternalLink className="h-3 w-3" />
                </a>
              )}
              {certificate.certificate_file_name ? (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span>Certificate file: {certificate.certificate_file_name}</span>
                  <Button variant="outline" size="sm" onClick={() => openFile(certificate.id, "certificate")}>
                    View
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => void removeFile(certificate.id, "certificate")}>
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
                      void upload(certificate.id, "certificate", event.currentTarget.files?.[0]);
                      event.currentTarget.value = "";
                    }}
                  />
                  {certificate.certificate_file_name ? "Replace certificate file" : "Add certificate file"}
                </Label>
                {certificate.badge_image_name ? (
                  <>
                    <span className="text-sm text-muted-foreground">
                      Badge: {certificate.badge_image_name}
                    </span>
                    <Button variant="outline" size="sm" onClick={() => openFile(certificate.id, "badge")}>
                      View badge
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void removeFile(certificate.id, "badge")}>
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
                        void upload(certificate.id, "badge", event.currentTarget.files?.[0]);
                        event.currentTarget.value = "";
                      }}
                    />
                    Add badge image
                  </Label>
                )}
                {certificate.badge_url && (
                  <a className="text-sm text-primary underline" href={certificate.badge_url} target="_blank" rel="noreferrer">
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
                    <Button variant="ghost" size="sm" onClick={() => void revoke(certificate.id)}>
                      Stop sharing
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={shareCertificate.isPending}
                    onClick={() => void share(certificate.id)}
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
        title={editingId ? "Edit certificate" : "Add certificate"}
      >
        <form className="flex flex-col gap-4" onSubmit={(event) => void saveCertificate(event)}>
          <Field label="Certificate name" required>
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
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add certificate"}
          </Button>
        </form>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            deleteCertificate.mutate(deleteTarget.id, {
              onSuccess: () => setDeleteTarget(null),
            });
          }
        }}
        title="Delete certificate?"
        description={
          deleteTarget
            ? `Remove "${deleteTarget.name}" from your certificate library? This can't be undone.`
            : ""
        }
        isPending={deleteCertificate.isPending}
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
