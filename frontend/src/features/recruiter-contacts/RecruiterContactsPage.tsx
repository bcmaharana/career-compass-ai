import {
  useAddRecruiterContactNote,
  useCreateRecruiterContact,
  useDeleteRecruiterContact,
  useRecruiterContacts,
  useUpdateRecruiterContact,
} from "@/api/queries/recruiter-contacts";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDisplayDate } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

type RecruiterContact = components["schemas"]["RecruiterContactResponse"];

interface FormState {
  name: string;
  email: string;
  phone: string;
  company: string;
  linkedin_url: string;
  role_title: string;
}

const EMPTY_FORM: FormState = {
  name: "",
  email: "",
  phone: "",
  company: "",
  linkedin_url: "",
  role_title: "",
};

function toFormState(contact: RecruiterContact): FormState {
  return {
    name: contact.name,
    email: contact.email ?? "",
    phone: contact.phone ?? "",
    company: contact.company ?? "",
    linkedin_url: contact.linkedin_url ?? "",
    role_title: contact.role_title ?? "",
  };
}

/**
 * A standalone, reusable address book — a recruiter/contact can be
 * created here independent of any Job Application, then linked from
 * one (or several) later. See app/domain/job_application_tracking/entities.py.
 */
export function RecruiterContactsPage() {
  const { data: contacts, isLoading } = useRecruiterContacts();
  const createContact = useCreateRecruiterContact();
  const updateContact = useUpdateRecruiterContact();
  const deleteContact = useDeleteRecruiterContact();
  const addNote = useAddRecruiterContactNote();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [deleteTarget, setDeleteTarget] = useState<RecruiterContact | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});

  function openAddDialog() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  }

  function openEditDialog(contact: RecruiterContact) {
    setEditingId(contact.id);
    setForm(toFormState(contact));
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
    const body = {
      name: form.name,
      email: form.email || null,
      phone: form.phone || null,
      company: form.company || null,
      linkedin_url: form.linkedin_url || null,
      role_title: form.role_title || null,
    };

    const mutation = editingId
      ? updateContact.mutateAsync({ id: editingId, body })
      : createContact.mutateAsync(body);
    mutation.then(() => setDialogOpen(false)).catch(() => {});
  }

  function handleAddNote(contactId: string) {
    const note = (noteDrafts[contactId] ?? "").trim();
    if (!note) return;
    addNote
      .mutateAsync({
        id: contactId,
        body: { note, note_date: new Date().toISOString().slice(0, 10) },
      })
      .then(() => setNoteDrafts((prev) => ({ ...prev, [contactId]: "" })))
      .catch(() => {});
  }

  const isSaving = createContact.isPending || updateContact.isPending;
  const saveError = createContact.error ?? updateContact.error;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <CardTitle>Recruiter Contacts</CardTitle>
          <Button variant="ghost" size="sm" onClick={openAddDialog}>
            <Plus className="h-3.5 w-3.5" />
            Add
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
          {contacts?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No contacts yet — add a recruiter or hiring contact, whether or not you've linked
              them to an application yet.
            </p>
          )}
          {contacts?.map((contact) => {
            const isExpanded = expandedIds.has(contact.id);
            return (
              <div key={contact.id} className="rounded-md border border-border px-4 py-2">
                <div className="flex items-start justify-between gap-4">
                  <button
                    type="button"
                    onClick={() => toggleExpanded(contact.id)}
                    className="flex-1 text-left"
                  >
                    <p className="text-sm font-medium">{contact.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {[contact.role_title, contact.company].filter(Boolean).join(" at ")}
                    </p>
                    {(contact.email || contact.phone) && (
                      <p className="text-xs text-muted-foreground">
                        {[contact.email, contact.phone].filter(Boolean).join(" · ")}
                      </p>
                    )}
                  </button>
                  <div className={`flex shrink-0 items-center ${ACTION_BUTTON_ROW_GAP}`}>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => toggleExpanded(contact.id)}
                      aria-label={isExpanded ? "Hide contact history" : "Show contact history"}
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
                      onClick={() => openEditDialog(contact)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => setDeleteTarget(contact)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
                    <p className="text-xs font-semibold uppercase text-muted-foreground">
                      Contact History
                    </p>
                    {contact.contact_history.length === 0 && (
                      <p className="text-sm text-muted-foreground">No notes yet.</p>
                    )}
                    {contact.contact_history.map((entry, i) => (
                      <div key={i} className="text-sm">
                        <span className="text-xs text-muted-foreground">
                          {formatDisplayDate(entry.date)}:
                        </span>{" "}
                        {entry.note}
                      </div>
                    ))}
                    <div className="flex gap-2 pt-1">
                      <Input
                        placeholder="Add a note (e.g. Called, discussed timeline)"
                        value={noteDrafts[contact.id] ?? ""}
                        onChange={(e) =>
                          setNoteDrafts((prev) => ({ ...prev, [contact.id]: e.target.value }))
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            handleAddNote(contact.id);
                          }
                        }}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={!(noteDrafts[contact.id] ?? "").trim() || addNote.isPending}
                        onClick={() => handleAddNote(contact.id)}
                      >
                        Add note
                      </Button>
                    </div>
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
        title={editingId ? "Edit contact" : "Add contact"}
      >
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rc-name">Name</Label>
            <Input
              id="rc-name"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rc-role-title">Role / title</Label>
            <Input
              id="rc-role-title"
              value={form.role_title}
              onChange={(e) => setForm({ ...form, role_title: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rc-company">Company / agency</Label>
            <Input
              id="rc-company"
              value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rc-email">Email</Label>
            <Input
              id="rc-email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rc-phone">Phone</Label>
            <Input
              id="rc-phone"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rc-linkedin">LinkedIn URL</Label>
            <Input
              id="rc-linkedin"
              type="url"
              value={form.linkedin_url}
              onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })}
            />
          </div>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : editingId ? "Save changes" : "Add contact"}
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
          if (deleteTarget) deleteContact.mutate(deleteTarget.id);
          setDeleteTarget(null);
        }}
        title="Delete this contact?"
        description={deleteTarget ? `Remove "${deleteTarget.name}"? This can't be undone.` : ""}
        isPending={deleteContact.isPending}
      />
    </div>
  );
}
