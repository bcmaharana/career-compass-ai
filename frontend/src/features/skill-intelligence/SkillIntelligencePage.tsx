import { GapAnalysisSection } from "@/features/skill-intelligence/GapAnalysisSection";
import { MySkillsSection } from "@/features/skill-intelligence/MySkillsSection";
import { TargetRoleSkillsSection } from "@/features/skill-intelligence/TargetRoleSkillsSection";

/**
 * Phase 3 — Skill Intelligence. Three fixed sections (not user-reorderable,
 * unlike Career Profile's sections): a self-service skill inventory, a
 * target-role requirements editor, and the blended gap analysis view that
 * cross-references both. See docs/architecture for the full domain model.
 */
export function SkillIntelligencePage() {
  return (
    <div className="grid gap-3">
      <MySkillsSection cardBackground="card" />
      <TargetRoleSkillsSection cardBackground="background" />
      <GapAnalysisSection cardBackground="card" />
    </div>
  );
}
