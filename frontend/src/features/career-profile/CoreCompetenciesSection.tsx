import { useCareerProfile, useUpdateCareerProfile } from "@/api/queries/career-profile";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { Input } from "@/components/ui/input";
import { MoveButtons } from "@/components/ui/move-buttons";
import type { SectionOrderProps } from "@/features/career-profile/section-order";
import { getErrorMessage } from "@/lib/errors";
import { X } from "lucide-react";
import { type KeyboardEvent, useState } from "react";

/**
 * Split out of ProfileHeader.tsx into its own card, shown above Career
 * Highlights, per explicit request. Shares the same `useCareerProfile`
 * cache and `useUpdateCareerProfile` mutation as ProfileHeader but owns
 * its own edit state independently, the same way every other
 * career-profile section does.
 */
export function CoreCompetenciesSection({
  onMoveUp,
  onMoveDown,
  isFirst,
  isLast,
  moveDisabled,
  cardBackground,
}: SectionOrderProps) {
  const { data: profile } = useCareerProfile();
  const updateProfile = useUpdateCareerProfile();

  const [isEditing, setIsEditing] = useState(false);
  const [isOpen, setIsOpen] = useState(true);
  const [competencies, setCompetencies] = useState<string[]>([]);
  const [competencyInput, setCompetencyInput] = useState("");

  function openEdit() {
    setCompetencies(profile?.core_competencies ?? []);
    setIsEditing(true);
  }

  /**
   * Commits the current competencyInput text into the competencies
   * array (if non-empty and not already present), clears the input, and
   * returns the resulting array — used by both the Enter/comma keydown
   * handler and handleSave, so "click Save without pressing Enter
   * first" and "press Enter" behave identically (see ProfileHeader.tsx
   * for the real bug this fixes — competencies typed but not committed
   * were silently dropped on Save).
   */
  function commitPendingCompetency(): string[] {
    const value = competencyInput.trim();
    if (!value || competencies.includes(value)) {
      return competencies;
    }
    const updated = [...competencies, value];
    setCompetencies(updated);
    setCompetencyInput("");
    return updated;
  }

  function addCompetency(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter" && event.key !== ",") return;
    event.preventDefault();
    commitPendingCompetency();
  }

  function removeCompetency(value: string) {
    setCompetencies(competencies.filter((c) => c !== value));
  }

  async function handleSave() {
    const finalCompetencies = commitPendingCompetency();
    try {
      // headline/summary are resent unchanged from the shared cache —
      // unlike core_competencies itself, the backend overwrites
      // headline/summary unconditionally on every call (see
      // CareerProfileService.update), so omitting them here would wipe
      // them out rather than leave them alone.
      await updateProfile.mutateAsync({
        headline: profile?.headline ?? null,
        summary: profile?.summary ?? null,
        core_competencies: finalCompetencies,
      });
      setIsEditing(false);
    } catch {
      // Error is surfaced via updateProfile.isError/error below —
      // edit mode deliberately stays open so nothing typed is lost.
    }
  }

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Core Competencies</CardTitle>
        <div className="flex items-center gap-1">
          {!isEditing && (
            <Button variant="outline" size="sm" onClick={openEdit}>
              Edit
            </Button>
          )}
          <CollapseToggle
            isOpen={isOpen}
            onToggle={() => setIsOpen(!isOpen)}
            label="Core Competencies"
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
        <CardContent>
          {isEditing ? (
            <div className="flex flex-col gap-1.5">
              <Input
                value={competencyInput}
                onChange={(e) => setCompetencyInput(e.target.value)}
                onKeyDown={addCompetency}
                onBlur={commitPendingCompetency}
                placeholder="Type a competency and press Enter (or just click away/Save)"
              />
              {competencies.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {competencies.map((c) => (
                    <Badge key={c} variant="accent" className="gap-1">
                      {c}
                      <button
                        type="button"
                        onClick={() => removeCompetency(c)}
                        aria-label={`Remove ${c}`}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
              <div className="mt-2 flex gap-2">
                <Button onClick={handleSave} disabled={updateProfile.isPending}>
                  {updateProfile.isPending ? "Saving..." : "Save"}
                </Button>
                <Button variant="ghost" onClick={() => setIsEditing(false)}>
                  Cancel
                </Button>
              </div>
              {updateProfile.isError && (
                <p role="alert" className="mt-2 text-sm text-destructive">
                  {getErrorMessage(updateProfile.error)}
                </p>
              )}
            </div>
          ) : profile && profile.core_competencies.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {profile.core_competencies.map((c) => (
                <Badge key={c} variant="accent">
                  {c}
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No competencies added yet.</p>
          )}
        </CardContent>
      )}
    </Card>
  );
}
