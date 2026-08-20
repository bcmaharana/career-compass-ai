import { useGapAnalysis } from "@/api/queries/skill-intelligence";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { itemAlternateClass } from "@/features/career-profile/section-order";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

interface GapAnalysisSectionProps {
  cardBackground: "card" | "background";
  /** Expand/collapse now lives in SkillIntelligencePage's shared
   * `expandedSection` state (single-open-accordion across all three
   * sections on that page), not a local `useState` here. */
  isOpen: boolean;
  onToggleOpen: () => void;
}

/**
 * Target-role-driven gaps only (per ADR-005) — required skills missing
 * per linked target role, computed by comparing each role's
 * required_skills against CareerProfile.core_competencies
 * case-insensitively. The catalog-driven "core gaps" half was dropped
 * entirely along with the skill_intelligence catalog (categories no
 * longer exist to drive it).
 */
export function GapAnalysisSection({ cardBackground, isOpen, onToggleOpen }: GapAnalysisSectionProps) {
  const { data: gapAnalysis, isLoading } = useGapAnalysis();
  // Closed by default, independent per role — clicking a role's row
  // reveals its missing-skills badges (direct 2026-08-20 request: "sub
  // cards ... should be implementing hide and show using clicks").
  const [expandedRoleIds, setExpandedRoleIds] = useState<Set<string>>(new Set());

  function toggleRoleExpanded(id: string) {
    setExpandedRoleIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  const hasTargetRoleGaps = (gapAnalysis?.target_role_gaps.length ?? 0) > 0;

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader
        role="button"
        tabIndex={0}
        aria-expanded={isOpen}
        onClick={onToggleOpen}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggleOpen();
          }
        }}
        className="flex-row cursor-pointer select-none items-start justify-between space-y-0"
      >
        <CardTitle>Gap Analysis</CardTitle>
        {isOpen ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </CardHeader>
      {isOpen && (
        <CardContent className="flex flex-col gap-2">
          {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
          {!hasTargetRoleGaps && !isLoading && (
            <p className="text-sm text-muted-foreground">
              No target-role gaps — either every required skill is covered, or no target roles
              have required skills linked yet.
            </p>
          )}
          {gapAnalysis?.target_role_gaps.map((gap, index) => {
            const isRoleExpanded = expandedRoleIds.has(gap.target_role_id);
            return (
              <div
                key={gap.target_role_id}
                className={cn(
                  "flex flex-col gap-2 rounded-md border border-border p-4",
                  itemAlternateClass(cardBackground, index),
                )}
              >
                <div
                  role="button"
                  tabIndex={0}
                  aria-expanded={isRoleExpanded}
                  onClick={() => toggleRoleExpanded(gap.target_role_id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      toggleRoleExpanded(gap.target_role_id);
                    }
                  }}
                  className="flex cursor-pointer select-none items-center justify-between gap-2"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="accent">{gap.tag}</Badge>
                    <p className="text-sm font-medium md:text-base">
                      {gap.role_name}{" "}
                      <span className="text-sm font-normal italic text-muted-foreground">
                        ({gap.missing_skills.length})
                      </span>
                    </p>
                  </div>
                  {isRoleExpanded ? (
                    <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                </div>
                {isRoleExpanded && (
                  <div className="flex flex-wrap gap-1.5">
                    {gap.missing_skills.map((skill) => (
                      <Badge key={skill} variant="destructive">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </CardContent>
      )}
    </Card>
  );
}
