import type { components } from "@/api/schema.gen";
import {
  useAddTargetRole,
  useDeleteTargetRole,
  useTargetRoles,
  useUpdateTargetRole,
} from "@/api/queries/career-profile";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tooltip } from "@/components/ui/tooltip";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Pencil, Plus, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

type TargetRole = components["schemas"]["TargetRoleResponse"];

const MAX_TARGET_ROLES = 10;
const TAG_MAX_LENGTH = 3;

/**
 * Right Nav lower section for the Career Profile page specifically (UI
 * enhancement brief Part 2.5) — up to 10 current/future target roles,
 * each with a short (<=3 char) tag, e.g. "EAC" for "Enterprise Agile
 * Coach". Deliberately just entry/rename/removal this round: the
 * brief's explicit future scope is tagging other profile items against
 * these roles — realized as the Master/Target-Role-Profile switcher: each
 * row navigates to `/profile?role=<id>` (Career Profile page reads that
 * param via ProfileScopeContext), and a pinned "Master Profile" row above
 * the list navigates back to the unscoped `/profile`. Active state is
 * derived from the URL, not local component state, so it survives a
 * refresh and stays in sync if the URL changes some other way.
 */
export function TargetRolesWidget() {
  const { data: targetRoles } = useTargetRoles();
  const addTargetRole = useAddTargetRole();
  const updateTargetRole = useUpdateTargetRole();
  const deleteTargetRole = useDeleteTargetRole();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const activeRoleId = searchParams.get("role");

  const [formOpen, setFormOpen] = useState(false);
  const [tag, setTag] = useState("");
  const [roleName, setRoleName] = useState("");

  const [editing, setEditing] = useState<TargetRole | null>(null);
  const [editTag, setEditTag] = useState("");
  const [editRoleName, setEditRoleName] = useState("");

  const [deleteTarget, setDeleteTarget] = useState<TargetRole | null>(null);

  const count = targetRoles?.length ?? 0;
  const atLimit = count >= MAX_TARGET_ROLES;

  function handleAdd(event: FormEvent) {
    event.preventDefault();
    const trimmedTag = tag.trim();
    const trimmedName = roleName.trim();
    if (!trimmedTag || !trimmedName || atLimit) return;
    addTargetRole.mutate(
      { tag: trimmedTag, role_name: trimmedName },
      {
        onSuccess: () => {
          setTag("");
          setRoleName("");
          setFormOpen(false);
        },
      },
    );
  }

  function closeForm() {
    setFormOpen(false);
    setTag("");
    setRoleName("");
  }

  function openEdit(role: TargetRole) {
    setEditing(role);
    setEditTag(role.tag);
    setEditRoleName(role.role_name);
  }

  function handleEditSave(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const trimmedTag = editTag.trim();
    const trimmedName = editRoleName.trim();
    if (!trimmedTag || !trimmedName) return;
    updateTargetRole.mutate(
      { id: editing.id, body: { tag: trimmedTag, role_name: trimmedName } },
      { onSuccess: () => setEditing(null) },
    );
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      <button
        type="button"
        onClick={() => navigate("/profile")}
        className={cn(
          "flex items-center justify-between rounded-md px-2 py-1 text-left text-[11px] font-semibold",
          activeRoleId === null
            ? "bg-card text-foreground"
            : "bg-card/60 text-primary-foreground hover:bg-card",
        )}
      >
        Master Profile
      </button>

      <div className="flex items-center justify-between">
        <h2 className="font-display text-[11px] font-semibold text-primary-foreground">
          Target Roles
        </h2>
        <span className="text-[11px] text-primary-foreground/70">
          {count}/{MAX_TARGET_ROLES}
        </span>
      </div>

      <ul className="flex flex-col gap-1.5">
        {targetRoles?.map((role) => (
          <li key={role.id}>
            <div
              className={cn(
                "flex items-center justify-between gap-2 rounded-md px-2 py-1 text-[11px]",
                activeRoleId === role.id
                  ? "bg-card text-foreground"
                  : "bg-card/60 text-primary-foreground hover:bg-card",
              )}
            >
              <button
                type="button"
                onClick={() => navigate(`/profile?role=${role.id}`)}
                className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
              >
                <Tooltip content={role.role_name} className="flex min-w-0 items-center gap-1.5">
                  <Badge variant="accent" className="shrink-0 px-1.5 py-0 text-[10px]">
                    {role.tag}
                  </Badge>
                  <span className="truncate">{role.role_name}</span>
                </Tooltip>
              </button>
              <div className="flex shrink-0 items-center gap-0.5">
                <button
                  type="button"
                  onClick={() => openEdit(role)}
                  aria-label={`Edit ${role.role_name}`}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setDeleteTarget(role)}
                  aria-label={`Remove ${role.role_name}`}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </li>
        ))}
        {count === 0 && (
          <li className="text-[11px] text-primary-foreground/70">
            No target roles yet — add up to {MAX_TARGET_ROLES}.
          </li>
        )}
      </ul>

      {!atLimit && !formOpen && (
        <button
          type="button"
          onClick={() => setFormOpen(true)}
          className="flex items-center justify-center gap-1.5 rounded-md bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] py-1.5 text-[11px] font-semibold text-primary transition-opacity hover:opacity-90"
        >
          <Plus className="h-3.5 w-3.5" />
          Add target role
        </button>
      )}

      {!atLimit && formOpen && (
        <form onSubmit={handleAdd} className="flex flex-col gap-1.5">
          <div className="flex items-center gap-1.5">
            <input
              value={tag}
              onChange={(e) => setTag(e.target.value.slice(0, TAG_MAX_LENGTH))}
              placeholder="EAC"
              maxLength={TAG_MAX_LENGTH}
              aria-label="Tag (up to 3 characters)"
              autoFocus
              className="h-7 w-12 shrink-0 rounded-md border border-border bg-card px-1.5 text-center text-[11px] uppercase outline-none focus:ring-2 focus:ring-ring"
            />
            <input
              value={roleName}
              onChange={(e) => setRoleName(e.target.value)}
              placeholder="e.g. Enterprise Agile Coach"
              className="h-7 flex-1 rounded-md border border-border bg-card px-2 text-[11px] outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              type="submit"
              variant="ghost"
              size="sm"
              disabled={!tag.trim() || !roleName.trim() || addTargetRole.isPending}
              className="h-6 px-2 text-[11px] text-primary-foreground/70 hover:bg-white/10 hover:text-primary-foreground"
            >
              {addTargetRole.isPending ? "Adding..." : "Add"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={closeForm}
              className="h-6 px-2 text-[11px] text-primary-foreground/70 hover:bg-white/10 hover:text-primary-foreground"
            >
              Cancel
            </Button>
          </div>
        </form>
      )}
      {addTargetRole.isError && (
        <p role="alert" className="text-[11px] text-destructive">
          {getErrorMessage(addTargetRole.error)}
        </p>
      )}

      <Dialog open={editing !== null} onClose={() => setEditing(null)} title="Edit target role">
        <form className="flex flex-col gap-4" onSubmit={handleEditSave}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="target-role-tag">Tag (up to 3 characters)</Label>
            <Input
              id="target-role-tag"
              required
              maxLength={TAG_MAX_LENGTH}
              value={editTag}
              onChange={(e) => setEditTag(e.target.value.slice(0, TAG_MAX_LENGTH).toUpperCase())}
              className="uppercase"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="target-role-name">Role name</Label>
            <Input
              id="target-role-name"
              required
              value={editRoleName}
              onChange={(e) => setEditRoleName(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={updateTargetRole.isPending}>
            {updateTargetRole.isPending ? "Saving..." : "Save"}
          </Button>
          {updateTargetRole.isError && (
            <p role="alert" className="text-sm text-destructive">
              {getErrorMessage(updateTargetRole.error)}
            </p>
          )}
        </form>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) {
            deleteTargetRole.mutate(deleteTarget.id);
            // The role's own Target Role Profile (headline, experience,
            // etc.) isn't deleted — it just becomes unreachable, since
            // nothing else links to it once the role itself is gone (see
            // TargetRoleService docstring). Navigate away from a URL
            // that's about to point at nothing.
            if (activeRoleId === deleteTarget.id) navigate("/profile");
          }
          setDeleteTarget(null);
        }}
        title="Delete target role?"
        description={
          deleteTarget
            ? `Remove "${deleteTarget.role_name}" (${deleteTarget.tag})? Any profile data you've built for this role (experience, education, etc.) stays in the database but becomes inaccessible — it isn't deleted, just unreachable. This can't be undone.`
            : ""
        }
        isPending={deleteTargetRole.isPending}
      />
    </div>
  );
}
