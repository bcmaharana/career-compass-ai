import { useCareerProfile, useUpdateCareerProfile } from "@/api/queries/career-profile";
import { Button } from "@/components/ui/button";
import { ACTION_BUTTON_ROW_GAP } from "@/components/ui/button-variants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { RichTextDisplay, RichTextEditor } from "@/components/ui/rich-text-editor";
import { useProfileScope } from "@/features/career-profile/profile-scope";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Eraser } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * Split out of ProfileHeader.tsx so it can scroll normally beneath the
 * now-sticky photo/headline strip (UI enhancement brief Part 2.4) — a
 * fixed second card, right after ProfileHeader and before the
 * user-reorderable sections (see CareerProfilePage.tsx); not part of
 * that reorderable list itself, the same as ProfileHeader.
 *
 * "Executive Summary" here is the same backend field as `summary` —
 * there's no separate "About" field; the profile's `headline` (still
 * edited in ProfileHeader) already serves as the short one-line version,
 * and `summary` is the longer overview this card edits, per the Phase 2
 * follow-up decision.
 */
export function ExecutiveSummarySection() {
  const scope = useProfileScope();
  const { data: profile } = useCareerProfile(scope);
  const updateProfile = useUpdateCareerProfile(scope);

  const [isEditing, setIsEditing] = useState(false);
  const [isOpen, setIsOpen] = useState(true);
  const [summary, setSummary] = useState("");
  const [clearOpen, setClearOpen] = useState(false);

  // This component doesn't remount when the Master/Target-Role-Profile
  // switcher (TargetRolesWidget.tsx) changes `scope` — same instance,
  // just refetching via a different query key — so without this, a
  // section collapsed while looking at one role's summary silently
  // stayed collapsed after switching to a different role's, hiding that
  // role's summary by default instead of showing it. Also drops out of
  // edit mode: staying in it across a scope change would otherwise leave
  // the edit form showing the *previous* role's summary text next to the
  // newly-loaded role's data underneath.
  useEffect(() => {
    setIsOpen(true);
    setIsEditing(false);
  }, [scope]);

  function openEdit() {
    setSummary(profile?.summary ?? "");
    setIsEditing(true);
  }

  async function handleClear() {
    try {
      await updateProfile.mutateAsync({
        headline: profile?.headline ?? null,
        summary: null,
      });
    } finally {
      setClearOpen(false);
    }
  }

  async function handleSave() {
    try {
      // headline/core_competencies/section_order are resent unchanged
      // (read from the shared cache) — the backend overwrites headline
      // unconditionally on every call (see CareerProfileService.update),
      // so omitting it here would wipe it out rather than leave it alone.
      await updateProfile.mutateAsync({
        headline: profile?.headline ?? null,
        summary: summary || null,
      });
      setIsEditing(false);
    } catch {
      // Error is surfaced via updateProfile.isError/error below —
      // edit mode deliberately stays open so nothing typed is lost.
    }
  }

  return (
    // Background is hardcoded (not a cardBackground prop like the
    // reorderable sections) — this card's position is fixed, always
    // second, right after the white ProfileHeader, so its alternation
    // never needs to change dynamically the way a reorderable section's
    // does (see section-order.ts).
    <Card className="bg-background">
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <CardTitle>Executive Summary</CardTitle>
        <div className={cn("flex items-start", ACTION_BUTTON_ROW_GAP)}>
          {!isEditing && (
            <Button variant="ghost" size="sm" onClick={openEdit}>
              Edit
            </Button>
          )}
          {!isEditing && !!profile?.summary && (
            <Button variant="ghost" size="sm" onClick={() => setClearOpen(true)}>
              <Eraser className="h-4 w-4" />
              Clear
            </Button>
          )}
          <CollapseToggle
            isOpen={isOpen}
            onToggle={() => setIsOpen(!isOpen)}
            label="Executive Summary"
          />
        </div>
      </CardHeader>
      {isOpen && (
        <CardContent>
          {isEditing ? (
            <div className="flex flex-col gap-3">
              <RichTextEditor
                defaultValue={summary}
                onChange={setSummary}
                placeholder="A short overview of your professional background"
                autoFocus
              />
              <div className="flex gap-2">
                <Button onClick={handleSave} disabled={updateProfile.isPending}>
                  {updateProfile.isPending ? "Saving..." : "Save"}
                </Button>
                <Button variant="ghost" onClick={() => setIsEditing(false)}>
                  Cancel
                </Button>
              </div>
              {updateProfile.isError && (
                <p role="alert" className="text-sm text-destructive">
                  {getErrorMessage(updateProfile.error)}
                </p>
              )}
            </div>
          ) : profile?.summary ? (
            <RichTextDisplay html={profile.summary} className="text-muted-foreground" />
          ) : (
            <p className="text-sm text-muted-foreground">
              No summary yet — add one to help your AI coach get to know you.
            </p>
          )}
        </CardContent>
      )}

      <ConfirmDialog
        open={clearOpen}
        onCancel={() => setClearOpen(false)}
        onConfirm={handleClear}
        title="Clear Executive Summary?"
        description="Remove your executive summary? This can't be undone."
        isPending={updateProfile.isPending}
        confirmLabel="Clear"
        confirmPendingLabel="Clearing..."
      />
    </Card>
  );
}
