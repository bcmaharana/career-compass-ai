import { useCareerProfile, useUpdateCareerProfile } from "@/api/queries/career-profile";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/errors";
import { useState } from "react";

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
  const { data: profile } = useCareerProfile();
  const updateProfile = useUpdateCareerProfile();

  const [isEditing, setIsEditing] = useState(false);
  const [isOpen, setIsOpen] = useState(true);
  const [summary, setSummary] = useState("");

  function openEdit() {
    setSummary(profile?.summary ?? "");
    setIsEditing(true);
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
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Executive Summary</CardTitle>
        <div className="flex items-center gap-1">
          {!isEditing && (
            <Button variant="outline" size="sm" onClick={openEdit}>
              Edit
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
              <Textarea
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                placeholder="A short overview of your professional background"
                rows={5}
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
          ) : (
            <p className="text-sm text-muted-foreground">
              {profile?.summary || "No summary yet — add one to help your AI coach get to know you."}
            </p>
          )}
        </CardContent>
      )}
    </Card>
  );
}
