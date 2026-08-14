import {
  useGrantPlatformAdmin,
  usePlatformAdminMe,
  usePlatformAdmins,
  usePlatformSettings,
  useRevokePlatformAdmin,
  useUpdatePlatformAdmin,
  useUpdatePlatformSetting,
} from "@/api/queries/platform-admin";
import type { components } from "@/api/schema.gen";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SystemStatusCard } from "@/features/dashboard/SystemStatusCard";
import { getErrorMessage } from "@/lib/errors";
import { type FormEvent, useState } from "react";

type PlatformSettingResponse = components["schemas"]["PlatformSettingResponse"];
type PlatformAdminGrantResponse = components["schemas"]["PlatformAdminGrantResponse"];

/**
 * A single ordered access level, not three independently-toggleable
 * permissions — each level's codes are a strict superset of the one
 * below it (Manage = full access, Edit = view+edit, View = view only),
 * so a radio group (pick exactly one) is the right control, not
 * checkboxes. The three underlying permission codes still exist on the
 * backend (require_platform_permission checks them individually), this
 * mapping just decides which combination a given level writes.
 */
type PermissionLevel = "view" | "edit" | "manage";

const PERMISSION_LEVELS: { value: PermissionLevel; label: string; description: string }[] = [
  { value: "view", label: "View", description: "Can view platform settings." },
  { value: "edit", label: "Edit", description: "Can view and edit platform settings." },
  {
    value: "manage",
    label: "Manage",
    description: "Full access — view/edit settings, plus grant or revoke other admins.",
  },
];

const LEVEL_CODES: Record<PermissionLevel, string[]> = {
  view: ["platform.settings.view"],
  edit: ["platform.settings.view", "platform.settings.edit"],
  manage: ["platform.settings.view", "platform.settings.edit", "platform.admins.manage"],
};

/** Highest level implied by an existing grant's raw codes — used to
 * seed the radio group when editing an admin whose codes might predate
 * this level model (e.g. an edit-only grant with no view code). */
function levelFromCodes(codes: string[]): PermissionLevel | null {
  if (codes.includes("platform.admins.manage")) return "manage";
  if (codes.includes("platform.settings.edit")) return "edit";
  if (codes.includes("platform.settings.view")) return "view";
  return null;
}

function PermissionLevelRadioGroup({
  name,
  value,
  onChange,
}: {
  name: string;
  value: PermissionLevel | null;
  onChange: (level: PermissionLevel) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      {PERMISSION_LEVELS.map((level) => (
        <label key={level.value} className="flex items-start gap-2 text-sm">
          <input
            type="radio"
            name={name}
            className="mt-0.5"
            checked={value === level.value}
            onChange={() => onChange(level.value)}
          />
          <span>
            {level.label}{" "}
            <span className="text-xs text-muted-foreground">— {level.description}</span>
          </span>
        </label>
      ))}
    </div>
  );
}

export function SettingsPlatformAdminPage() {
  const { data: me, isLoading } = usePlatformAdminMe();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  const canEditSettings = me?.permission_codes.includes("platform.settings.edit") ?? false;
  // Edit implies view — someone granted edit-only access could
  // otherwise edit a setting but never see it in the first place,
  // which isn't a real permission level anyone should end up in
  // (matches require_platform_permission's OR semantics on the
  // backend's GET /settings route).
  const canViewSettings =
    (me?.permission_codes.includes("platform.settings.view") ?? false) || canEditSettings;
  const canManageAdmins = me?.permission_codes.includes("platform.admins.manage") ?? false;

  if (!canViewSettings && !canManageAdmins) {
    return (
      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Platform Admin</CardTitle>
          <CardDescription>You don&apos;t have access to this page.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
      <div className="flex flex-col gap-6">
        {canViewSettings && <PlatformSettingsCard canEdit={canEditSettings} />}
        {canManageAdmins && <PlatformAdminsCard />}
      </div>
      <SystemStatusCard />
    </div>
  );
}

function PlatformSettingsCard({ canEdit }: { canEdit: boolean }) {
  const { data: settings, isLoading, isError, error } = usePlatformSettings(true);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Platform Settings</CardTitle>
        <CardDescription>
          Platform-wide configuration values — edits here take effect immediately, no redeploy
          needed.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {isError && (
          <p role="alert" className="text-sm text-destructive">
            {getErrorMessage(error)}
          </p>
        )}
        {settings?.length === 0 && (
          <p className="text-sm text-muted-foreground">No settings yet.</p>
        )}
        {settings?.map((setting) => (
          <PlatformSettingRow key={setting.id} setting={setting} canEdit={canEdit} />
        ))}
      </CardContent>
    </Card>
  );
}

function PlatformSettingRow({
  setting,
  canEdit,
}: {
  setting: PlatformSettingResponse;
  canEdit: boolean;
}) {
  const updateSetting = useUpdatePlatformSetting();
  const [value, setValue] = useState(setting.value);
  const [savedJustNow, setSavedJustNow] = useState(false);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSavedJustNow(false);
    updateSetting.mutate(
      { key: setting.key, body: { value, description: setting.description } },
      { onSuccess: () => setSavedJustNow(true) },
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-1.5 border-b border-border pb-4 last:border-0 last:pb-0"
    >
      <Label htmlFor={`setting-${setting.key}`}>{setting.key}</Label>
      {setting.description && (
        <p className="text-xs text-muted-foreground">{setting.description}</p>
      )}
      <div className="flex items-center gap-2">
        <Input
          id={`setting-${setting.key}`}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setSavedJustNow(false);
          }}
          disabled={!canEdit}
        />
        {canEdit && (
          <Button
            type="submit"
            disabled={updateSetting.isPending || value === setting.value}
          >
            {updateSetting.isPending ? "Saving..." : "Save"}
          </Button>
        )}
      </div>
      {savedJustNow && !updateSetting.isPending && (
        <span className="text-xs text-muted-foreground">Saved.</span>
      )}
      {updateSetting.isError && (
        <p role="alert" className="text-xs text-destructive">
          {getErrorMessage(updateSetting.error)}
        </p>
      )}
    </form>
  );
}

function PlatformAdminsCard() {
  const { data: admins, isLoading, isError, error } = usePlatformAdmins(true);

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>Platform Admins</CardTitle>
        <CardDescription>Grant or revoke platform-admin access, by email.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <GrantAdminForm />

        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {isError && (
          <p role="alert" className="text-sm text-destructive">
            {getErrorMessage(error)}
          </p>
        )}
        <div className="flex flex-col gap-4">
          {admins?.length === 0 && (
            <p className="text-sm text-muted-foreground">No platform admins yet.</p>
          )}
          {admins?.map((admin) => (
            <PlatformAdminRow key={admin.id} admin={admin} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function GrantAdminForm() {
  const grant = useGrantPlatformAdmin();
  const [email, setEmail] = useState("");
  const [subdomain, setSubdomain] = useState("");
  const [level, setLevel] = useState<PermissionLevel | null>(null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!level) return;
    grant.mutate(
      { email, subdomain: subdomain.trim() || null, permission_codes: LEVEL_CODES[level] },
      {
        onSuccess: () => {
          setEmail("");
          setSubdomain("");
          setLevel(null);
        },
      },
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-md border border-border p-4"
    >
      <p className="text-sm font-medium">Grant access</p>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="grant-email">Email</Label>
        <Input
          id="grant-email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="grant-subdomain">
          Organization subdomain (leave blank for a Personal account)
        </Label>
        <Input
          id="grant-subdomain"
          value={subdomain}
          onChange={(e) => setSubdomain(e.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <p className="text-sm">Access level</p>
        <PermissionLevelRadioGroup name="grant-level" value={level} onChange={setLevel} />
      </div>
      <div>
        <Button type="submit" disabled={grant.isPending || !level || !email}>
          {grant.isPending ? "Granting..." : "Grant access"}
        </Button>
      </div>
      {grant.isError && (
        <p role="alert" className="text-sm text-destructive">
          {getErrorMessage(grant.error)}
        </p>
      )}
    </form>
  );
}

function PlatformAdminRow({ admin }: { admin: PlatformAdminGrantResponse }) {
  const updateAdmin = useUpdatePlatformAdmin();
  const revokeAdmin = useRevokePlatformAdmin();
  const [level, setLevel] = useState<PermissionLevel | null>(
    levelFromCodes(admin.permission_codes),
  );
  const [confirmingRevoke, setConfirmingRevoke] = useState(false);

  const isDirty = level !== null && level !== levelFromCodes(admin.permission_codes);

  return (
    <div className="flex flex-col gap-2 rounded-md border border-border p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">{admin.full_name}</p>
          <p className="text-xs text-muted-foreground">
            {admin.email}
            {" — "}
            {admin.is_personal ? "Personal account" : `Enterprise · ${admin.subdomain}`}
          </p>
        </div>
        <Button variant="ghost" onClick={() => setConfirmingRevoke(true)}>
          Revoke
        </Button>
      </div>
      <PermissionLevelRadioGroup
        name={`admin-level-${admin.id}`}
        value={level}
        onChange={setLevel}
      />
      {isDirty && (
        <div>
          <Button
            onClick={() =>
              level &&
              updateAdmin.mutate({ id: admin.id, body: { permission_codes: LEVEL_CODES[level] } })
            }
            disabled={updateAdmin.isPending}
          >
            {updateAdmin.isPending ? "Saving..." : "Save changes"}
          </Button>
        </div>
      )}
      {updateAdmin.isError && (
        <p role="alert" className="text-xs text-destructive">
          {getErrorMessage(updateAdmin.error)}
        </p>
      )}
      {revokeAdmin.isError && (
        <p role="alert" className="text-xs text-destructive">
          {getErrorMessage(revokeAdmin.error)}
        </p>
      )}

      <ConfirmDialog
        open={confirmingRevoke}
        onCancel={() => setConfirmingRevoke(false)}
        onConfirm={() =>
          revokeAdmin.mutate(admin.id, { onSuccess: () => setConfirmingRevoke(false) })
        }
        title="Revoke platform admin access?"
        description={`This removes all platform.* permissions from ${admin.email}.`}
        isPending={revokeAdmin.isPending}
        confirmLabel="Revoke"
        confirmPendingLabel="Revoking..."
      />
    </div>
  );
}
