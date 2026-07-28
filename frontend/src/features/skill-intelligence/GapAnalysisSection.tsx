import { useGapAnalysis } from "@/api/queries/skill-intelligence";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapseToggle } from "@/components/ui/collapse-toggle";
import { itemAlternateClass } from "@/features/career-profile/section-order";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface GapAnalysisSectionProps {
  cardBackground: "card" | "background";
}

/**
 * Target-role-driven gaps only (per ADR-005) — required skills missing
 * per linked target role, computed by comparing each role's
 * required_skills against CareerProfile.core_competencies
 * case-insensitively. The catalog-driven "core gaps" half was dropped
 * entirely along with the skill_intelligence catalog (categories no
 * longer exist to drive it).
 */
export function GapAnalysisSection({ cardBackground }: GapAnalysisSectionProps) {
  const { data: gapAnalysis, isLoading } = useGapAnalysis();
  const [isOpen, setIsOpen] = useState(true);

  const hasTargetRoleGaps = (gapAnalysis?.target_role_gaps.length ?? 0) > 0;

  return (
    <Card className={cardBackground === "background" ? "bg-background" : undefined}>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Gap Analysis</CardTitle>
        <CollapseToggle isOpen={isOpen} onToggle={() => setIsOpen(!isOpen)} label="Gap Analysis" />
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
          {gapAnalysis?.target_role_gaps.map((gap, index) => (
            <div
              key={gap.target_role_id}
              className={cn(
                "flex flex-col gap-2 rounded-md border border-border p-4",
                itemAlternateClass(cardBackground, index),
              )}
            >
              <div className="flex items-center gap-2">
                <Badge variant="accent">{gap.tag}</Badge>
                <p className="font-medium">{gap.role_name}</p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {gap.missing_skills.map((skill) => (
                  <Badge key={skill} variant="destructive">
                    {skill}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      )}
    </Card>
  );
}
