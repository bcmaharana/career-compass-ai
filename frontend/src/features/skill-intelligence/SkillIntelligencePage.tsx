import { GapAnalysisSection } from "@/features/skill-intelligence/GapAnalysisSection";
import { MySkillsSection } from "@/features/skill-intelligence/MySkillsSection";
import { TargetRoleSkillsSection } from "@/features/skill-intelligence/TargetRoleSkillsSection";
import { useState } from "react";

type SkillIntelligenceSectionId = "my-skills" | "target-role-skills" | "gap-analysis";

/**
 * Phase 3 — Skill Intelligence. Three fixed sections (not user-reorderable,
 * unlike Career Profile's sections): a self-service skill inventory, a
 * target-role requirements editor, and the blended gap analysis view that
 * cross-references both. See docs/architecture for the full domain model.
 *
 * Closed-by-default, click-header-to-expand, single-open accordion across
 * all three — same mechanism as DashboardPage.tsx's `expandedCard` and
 * CareerProfilePage.tsx's `expandedSection`, replacing each section's
 * former independent Eye/EyeOff CollapseToggle (all three previously
 * defaulted open).
 */
export function SkillIntelligencePage() {
  const [expandedSection, setExpandedSection] = useState<SkillIntelligenceSectionId | null>(null);

  function toggleSection(id: SkillIntelligenceSectionId) {
    setExpandedSection((prev) => (prev === id ? null : id));
  }

  return (
    <div className="grid gap-3">
      <MySkillsSection
        cardBackground="card"
        isOpen={expandedSection === "my-skills"}
        onToggleOpen={() => toggleSection("my-skills")}
      />
      <TargetRoleSkillsSection
        cardBackground="background"
        isOpen={expandedSection === "target-role-skills"}
        onToggleOpen={() => toggleSection("target-role-skills")}
      />
      <GapAnalysisSection
        cardBackground="card"
        isOpen={expandedSection === "gap-analysis"}
        onToggleOpen={() => toggleSection("gap-analysis")}
      />
    </div>
  );
}
