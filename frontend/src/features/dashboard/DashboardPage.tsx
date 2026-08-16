import {
  useCareerProfile,
  useCareerProfileSummary,
  useTargetRoles,
} from "@/api/queries/career-profile";
import { useLearningItems } from "@/api/queries/learning-intelligence";
import { useCareerPath, useJobListings } from "@/api/queries/opportunity-intelligence";
import { useResumeList } from "@/api/queries/resume-intelligence";
import { useGapAnalysis } from "@/api/queries/skill-intelligence";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineLink } from "@/components/ui/inline-link";
import { formatDisplayDate } from "@/lib/date-format";

type ResumeSummary = components["schemas"]["ResumeSummary"];
type TargetRoleResponse = components["schemas"]["TargetRoleResponse"];

/** The Master profile plus one entry per Target Role Profile — the same
 * scoping axis career-profile.ts's queries use (null = Master), reused
 * here so each of the three cards below can iterate "every profile this
 * person has" identically. */
function useProfileScopes(): { id: string | null; label: string }[] {
  const { data: targetRoles } = useTargetRoles();
  return [
    { id: null, label: "Master" },
    ...(targetRoles?.map((r: TargetRoleResponse) => ({ id: r.id, label: r.role_name })) ?? []),
  ];
}

/**
 * Three at-a-glance cards, each built entirely from data already fetched
 * elsewhere in the app (Career Profile summary, Skill Gap Analysis,
 * Resume Intelligence history) — no new backend endpoints. Replaced the
 * original Phase-0 placeholder cards (a raw health-check ping and a
 * "signed in as" debug readout), which had no product value once
 * System Status (Settings > Platform Admin) and the Right Nav identity
 * box existed to cover the same ground properly.
 */
export function DashboardPage() {
  return (
    <div className="flex max-w-xl flex-col gap-4">
      <ProfileCompletenessCard />
      <SkillIntelligenceCard />
      <ResumeIntelligenceCard />
      <OpportunityIntelligenceCard />
      <LearningIntelligenceCard />
    </div>
  );
}

function ProfileCompletenessCard() {
  const scopes = useProfileScopes();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Career Profile</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {scopes.map((scope) => (
          <ProfileCompletenessRow key={scope.id ?? "master"} scope={scope.id} label={scope.label} />
        ))}
        <InlineLink to="/profile" className="text-xs">
          Go to Career Profile
        </InlineLink>
      </CardContent>
    </Card>
  );
}

function ProfileCompletenessRow({ scope, label }: { scope: string | null; label: string }) {
  const { data: summary, isLoading } = useCareerProfileSummary(scope);

  // career_readiness_score is never computed anywhere in this codebase
  // yet (always null) — this simple 6-signal percentage is a real,
  // honest stand-in rather than surfacing a field that would always
  // read "--".
  const filledCount = summary
    ? [
        summary.has_headline,
        summary.has_summary,
        summary.competency_count > 0,
        summary.experience_count > 0,
        summary.education_count > 0,
        summary.certification_count > 0,
      ].filter(Boolean).length
    : 0;
  const percent = Math.round((filledCount / 6) * 100);

  return (
    <div className="flex items-center justify-between gap-2 border-b border-border pb-2 last:border-0 last:pb-0">
      <span className="truncate text-sm font-medium">{label}</span>
      {isLoading ? (
        <span className="text-xs text-muted-foreground">Loading...</span>
      ) : (
        <Badge variant={percent === 100 ? "accent" : "default"}>{percent}% complete</Badge>
      )}
    </div>
  );
}

/** Treated as "not really categorized" for the dashboard's uncategorized
 * count — both a blank/null category and the literal "Unknown" category
 * (the default a bulk comma-separated add assigns when no category was
 * typed — see buildCompetenciesFromAddInput) mean the same thing here:
 * nobody has sorted this skill into a real category yet. */
function isUncategorized(category: string | null | undefined): boolean {
  const trimmed = category?.trim() ?? "";
  return trimmed === "" || trimmed.toLowerCase() === "unknown";
}

function SkillIntelligenceCard() {
  const { data: gapAnalysis, isLoading: gapLoading } = useGapAnalysis();
  const { data: targetRoles, isLoading: rolesLoading } = useTargetRoles();
  const isLoading = gapLoading || rolesLoading;
  const roleCount = targetRoles?.length ?? 0;

  function missingSkillsFor(roleId: string): string[] {
    return (
      gapAnalysis?.target_role_gaps.find((g) => g.target_role_id === roleId)?.missing_skills ?? []
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Skill Intelligence</CardTitle>
        <CardDescription>
          {roleCount > 0
            ? `Across ${roleCount} target role${roleCount === 1 ? "" : "s"}`
            : "No target roles set yet"}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {!isLoading && roleCount === 0 && (
          <p className="text-sm text-muted-foreground">
            Add a target role to see which skills you&apos;re missing.
          </p>
        )}
        {!isLoading &&
          targetRoles?.map((role) => (
            <SkillIntelligenceRow key={role.id} role={role} missingSkills={missingSkillsFor(role.id)} />
          ))}
        <InlineLink to="/skills" className="text-xs">
          Go to Skill Intelligence
        </InlineLink>
      </CardContent>
    </Card>
  );
}

function SkillIntelligenceRow({
  role,
  missingSkills,
}: {
  role: TargetRoleResponse;
  missingSkills: string[];
}) {
  const { data: masterProfile } = useCareerProfile(null);
  const { data: roleProfile } = useCareerProfile(role.id);
  const missing = missingSkills.length;

  // A role with zero required_skills trivially has nothing "missing" —
  // the backend's gap list has no way to tell that apart from a role
  // that's genuinely fully matched (both just don't appear in
  // target_role_gaps), so that distinction has to be made here, from
  // required_skills itself, rather than reading "Fully matched" onto a
  // role nobody has ever defined requirements for.
  if (role.required_skills.length === 0) {
    return (
      <div className="flex items-center justify-between gap-2 border-b border-border pb-2 last:border-0 last:pb-0">
        <span className="truncate text-sm font-medium">{role.role_name}</span>
        <Badge variant="default">No requirements set</Badge>
      </div>
    );
  }

  // Category lookup, role-specific competencies taking precedence over
  // Master's — mirrors the backend's own Master-union-role "owned"
  // logic (see gap_analysis_service.py) for which competency actually
  // satisfies a given required skill.
  const categoryByName = new Map<string, string | null | undefined>();
  for (const c of masterProfile?.core_competencies ?? []) {
    categoryByName.set(c.name.toLowerCase(), c.category);
  }
  for (const c of roleProfile?.core_competencies ?? []) {
    categoryByName.set(c.name.toLowerCase(), c.category);
  }

  const missingLower = new Set(missingSkills.map((s) => s.toLowerCase()));
  const matchedSkills = role.required_skills.filter((s) => !missingLower.has(s.toLowerCase()));
  const uncategorizedCount = matchedSkills.filter((s) =>
    isUncategorized(categoryByName.get(s.toLowerCase())),
  ).length;

  return (
    <div className="flex items-center justify-between gap-2 border-b border-border pb-2 last:border-0 last:pb-0">
      <span className="truncate text-sm font-medium">{role.role_name}</span>
      <Badge variant={missing === 0 ? "accent" : "destructive"}>
        {missing === 0
          ? uncategorizedCount > 0
            ? `Fully matched/${uncategorizedCount} uncategorized`
            : "Fully matched"
          : `${missing} missing`}
      </Badge>
    </div>
  );
}

function ResumeIntelligenceCard() {
  const scopes = useProfileScopes();
  const { data: resumes } = useResumeList();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Resume Intelligence</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {scopes.map((scope) => (
          <ResumeStatusRow
            key={scope.id ?? "master"}
            scope={scope.id}
            label={scope.label}
            resumes={resumes ?? []}
          />
        ))}
        <InlineLink to="/resumes" className="text-xs">
          Go to Resume Intelligence
        </InlineLink>
      </CardContent>
    </Card>
  );
}

function ResumeStatusRow({
  scope,
  label,
  resumes,
}: {
  scope: string | null;
  label: string;
  resumes: ResumeSummary[];
}) {
  const { data: profile } = useCareerProfile(scope);

  // resumes is already ordered created_at desc (see list_for_user) —
  // filtering preserves that order, so the first match is the most
  // recent upload for this specific profile.
  const uploaded = resumes.find((r) => r.target_role_id === scope);
  const hasGenerated = Boolean(profile?.resume_docx_url || profile?.resume_pdf_url);
  const generatedAt = formatDisplayDate(profile?.resume_generated_at ?? null);

  return (
    <div className="flex flex-col gap-1 border-b border-border pb-2 last:border-0 last:pb-0">
      <span className="truncate text-sm font-medium">{label}</span>
      <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
        <span className="truncate">
          Uploaded:{" "}
          {uploaded
            ? `${uploaded.original_filename} · ${formatDisplayDate(uploaded.created_at)}`
            : "None"}
        </span>
        <span>Downloaded: {hasGenerated ? `generated ${generatedAt}` : "None"}</span>
      </div>
    </div>
  );
}

/** Scoped to the user's first target role only (not every role, unlike
 * the other cards above) — job listings and career path are both real
 * external/graph lookups, not free local computation, so the dashboard
 * deliberately doesn't fan out to every target role here. */
function OpportunityIntelligenceCard() {
  const { data: targetRoles, isLoading: rolesLoading } = useTargetRoles();
  const primaryRoleId = targetRoles?.[0]?.id ?? null;
  const { data: jobListings, isLoading: jobsLoading } = useJobListings(primaryRoleId);
  const { data: careerPath, isLoading: pathLoading } = useCareerPath(primaryRoleId);
  const isLoading = rolesLoading || jobsLoading || pathLoading;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Opportunity Intelligence</CardTitle>
        {targetRoles && targetRoles.length > 0 && (
          <CardDescription>For {targetRoles[0]!.role_name}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {!primaryRoleId && (
          <p className="text-sm text-muted-foreground">
            Add a target role to see matching job listings and a career path.
          </p>
        )}
        {primaryRoleId && isLoading && (
          <p className="text-sm text-muted-foreground">Loading...</p>
        )}
        {primaryRoleId && !isLoading && (
          <>
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">Job listings</span>
              <Badge variant="default">{jobListings?.listings.length ?? 0} found</Badge>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">Career path</span>
              <Badge variant={careerPath?.resolved ? "accent" : "default"}>
                {careerPath?.resolved ? "Available" : "No data yet"}
              </Badge>
            </div>
          </>
        )}
        <InlineLink to="/opportunities" className="text-xs">
          Go to Opportunity Intelligence
        </InlineLink>
      </CardContent>
    </Card>
  );
}

function LearningIntelligenceCard() {
  const { data: items, isLoading } = useLearningItems();
  const inProgressCount = items?.filter((i) => i.status === "in_progress").length ?? 0;
  const completedCount = items?.filter((i) => i.status === "completed").length ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Learning Intelligence</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
        {!isLoading && items?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No learning items yet — track courses, certs, or resources you're working toward.
          </p>
        )}
        {!isLoading && items && items.length > 0 && (
          <div className="flex items-center gap-2">
            <Badge variant="default">{items.length} total</Badge>
            <Badge variant="accent">{inProgressCount} in progress</Badge>
            <Badge variant="default">{completedCount} completed</Badge>
          </div>
        )}
        <InlineLink to="/learning" className="text-xs">
          Go to Learning Intelligence
        </InlineLink>
      </CardContent>
    </Card>
  );
}
