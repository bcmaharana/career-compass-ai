import {
  useCareerProfile,
  useCareerProfileSummary,
  useTargetRoles,
} from "@/api/queries/career-profile";
import { useInterviewPrepSummary } from "@/api/queries/interview-prep";
import { useJobApplicationsSummary } from "@/api/queries/job-application-tracking";
import { useLearningItems } from "@/api/queries/learning-intelligence";
import { useCareerPath, useJobListings } from "@/api/queries/opportunity-intelligence";
import { useResumeList } from "@/api/queries/resume-intelligence";
import { useGapAnalysis } from "@/api/queries/skill-intelligence";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineLink } from "@/components/ui/inline-link";
import { formatDisplayDate } from "@/lib/date-format";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

type ResumeSummary = components["schemas"]["ResumeSummary"];
type TargetRoleResponse = components["schemas"]["TargetRoleResponse"];

interface DashboardCardProps {
  isOpen: boolean;
  onToggle: () => void;
}

/**
 * Shared closed-by-default accordion shell for every Dashboard card — a
 * card starts collapsed (header + optional description only) and only
 * mounts its `children` (each card's own CardContent body) once opened,
 * so a collapsed card's own per-row hooks (e.g. ProfileCompletenessRow's
 * useCareerProfileSummary per scope) never even fire until the person
 * actually opens it — React never calls a child component's function
 * body for an element that isn't part of what gets returned to the
 * reconciler, so gating `children` behind `isOpen` here is enough; no
 * extra "enabled" plumbing needed on the individual query hooks. Single-
 * open behavior (opening one card closes whichever else was open) is
 * driven by DashboardPage's own `expandedCard` state, the same one-value
 * -not-independent-booleans shape InterviewPrepPage.tsx's
 * Topic/Question accordion already uses. The whole header is clickable
 * (not just the chevron), mirroring Interview Prep's own
 * click-anywhere-on-header card pattern.
 */
function DashboardCardShell({
  title,
  description,
  isOpen,
  onToggle,
  children,
}: {
  title: string;
  description?: ReactNode;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader
        role="button"
        tabIndex={0}
        aria-expanded={isOpen}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
        className="cursor-pointer select-none"
      >
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <CardTitle>{title}</CardTitle>
            {/* The description line (e.g. "Across 2 target roles") only
                shows once the card is open — direct feedback that it
                read as clutter sitting under the title on an otherwise
                collapsed, single-line card header. */}
            {isOpen && description}
          </div>
          {isOpen ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
        </div>
      </CardHeader>
      {isOpen && <CardContent className="flex flex-col gap-2">{children}</CardContent>}
    </Card>
  );
}

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
type DashboardCardId =
  | "profile"
  | "skills"
  | "resumes"
  | "opportunities"
  | "job-applications"
  | "learning"
  | "interview-prep";

export function DashboardPage() {
  // Single shared value (not one boolean per card) so opening a card
  // always closes whichever other one was open — same pattern this
  // app's other single-open accordions (e.g. Interview Prep's
  // Topics/Questions) already use. `null` = every card closed, the
  // default on a fresh page load.
  const [expandedCard, setExpandedCard] = useState<DashboardCardId | null>(null);

  function toggleCard(id: DashboardCardId) {
    setExpandedCard((prev) => (prev === id ? null : id));
  }

  return (
    <div className="flex max-w-xl flex-col gap-4">
      <ProfileCompletenessCard
        isOpen={expandedCard === "profile"}
        onToggle={() => toggleCard("profile")}
      />
      <SkillIntelligenceCard
        isOpen={expandedCard === "skills"}
        onToggle={() => toggleCard("skills")}
      />
      <ResumeIntelligenceCard
        isOpen={expandedCard === "resumes"}
        onToggle={() => toggleCard("resumes")}
      />
      <OpportunityIntelligenceCard
        isOpen={expandedCard === "opportunities"}
        onToggle={() => toggleCard("opportunities")}
      />
      <JobApplicationsCard
        isOpen={expandedCard === "job-applications"}
        onToggle={() => toggleCard("job-applications")}
      />
      <LearningIntelligenceCard
        isOpen={expandedCard === "learning"}
        onToggle={() => toggleCard("learning")}
      />
      <InterviewPrepCard
        isOpen={expandedCard === "interview-prep"}
        onToggle={() => toggleCard("interview-prep")}
      />
    </div>
  );
}

function ProfileCompletenessCard({ isOpen, onToggle }: DashboardCardProps) {
  const scopes = useProfileScopes();

  return (
    <DashboardCardShell title="Career Profile" isOpen={isOpen} onToggle={onToggle}>
      {scopes.map((scope) => (
        <ProfileCompletenessRow key={scope.id ?? "master"} scope={scope.id} label={scope.label} />
      ))}
      <InlineLink to="/profile" className="text-xs">
        Go to Career Profile
      </InlineLink>
    </DashboardCardShell>
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

function SkillIntelligenceCard({ isOpen, onToggle }: DashboardCardProps) {
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
    <DashboardCardShell
      title="Skill Intelligence"
      description={
        <CardDescription>
          {roleCount > 0
            ? `Across ${roleCount} target role${roleCount === 1 ? "" : "s"}`
            : "No target roles set yet"}
        </CardDescription>
      }
      isOpen={isOpen}
      onToggle={onToggle}
    >
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
    </DashboardCardShell>
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

function ResumeIntelligenceCard({ isOpen, onToggle }: DashboardCardProps) {
  const scopes = useProfileScopes();
  const { data: resumes } = useResumeList();

  return (
    <DashboardCardShell title="Resume Intelligence" isOpen={isOpen} onToggle={onToggle}>
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
    </DashboardCardShell>
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
function OpportunityIntelligenceCard({ isOpen, onToggle }: DashboardCardProps) {
  const { data: targetRoles, isLoading: rolesLoading } = useTargetRoles();
  const primaryRoleId = targetRoles?.[0]?.id ?? null;
  const { data: jobListings, isLoading: jobsLoading } = useJobListings(primaryRoleId);
  const { data: careerPath, isLoading: pathLoading } = useCareerPath(primaryRoleId);
  const isLoading = rolesLoading || jobsLoading || pathLoading;

  return (
    <DashboardCardShell
      title="Opportunity Intelligence"
      description={
        targetRoles && targetRoles.length > 0 ? (
          <CardDescription>For {targetRoles[0]!.role_name}</CardDescription>
        ) : undefined
      }
      isOpen={isOpen}
      onToggle={onToggle}
    >
      {!primaryRoleId && (
        <p className="text-sm text-muted-foreground">
          Add a target role to see matching job listings and a career path.
        </p>
      )}
      {primaryRoleId && isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
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
    </DashboardCardShell>
  );
}

const JOB_APPLICATION_STATUS_LABELS: Record<string, string> = {
  considering: "Considering",
  applied: "Applied",
  phone_screen: "Phone Screen",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  didnt_hear_back: "Didn't Hear Back",
  other: "Other",
};

/** Status pipeline breakdown + soonest upcoming interview + a
 * stuck-too-long nudge — all live-computed server-side
 * (JobApplicationSummaryService), no client-side aggregation. */
function JobApplicationsCard({ isOpen, onToggle }: DashboardCardProps) {
  const { data: summary, isLoading } = useJobApplicationsSummary();
  const hasAnyApplications = (summary?.status_counts.length ?? 0) > 0;

  return (
    <DashboardCardShell title="Job Applications" isOpen={isOpen} onToggle={onToggle}>
      {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
      {!isLoading && !hasAnyApplications && (
        <p className="text-sm text-muted-foreground">
          No applications tracked yet — add one, or start a JD Tailoring session from a Job
          Listing to have one created automatically.
        </p>
      )}
      {!isLoading && hasAnyApplications && summary && (
        <>
          <div className="flex flex-wrap gap-2">
            {summary.status_counts.map((sc) => (
              <Badge key={sc.status} variant="default">
                {sc.count} {JOB_APPLICATION_STATUS_LABELS[sc.status] ?? sc.status}
              </Badge>
            ))}
          </div>
          {summary.next_interview && (
            <p className="text-sm">
              Next interview: {summary.next_interview.stage_label} at{" "}
              {summary.next_interview.company} on{" "}
              {formatDisplayDate(summary.next_interview.round_date)}
            </p>
          )}
          {summary.stuck_count > 0 && (
            <Badge variant="destructive">
              {summary.stuck_count} need{summary.stuck_count === 1 ? "s" : ""} a follow-up
            </Badge>
          )}
        </>
      )}
      <InlineLink to="/job-applications" className="text-xs">
        Go to Job Applications
      </InlineLink>
    </DashboardCardShell>
  );
}

function LearningIntelligenceCard({ isOpen, onToggle }: DashboardCardProps) {
  const { data: items, isLoading } = useLearningItems();
  const inProgressCount = items?.filter((i) => i.status === "in_progress").length ?? 0;
  const completedCount = items?.filter((i) => i.status === "completed").length ?? 0;

  return (
    <DashboardCardShell title="Learning Intelligence" isOpen={isOpen} onToggle={onToggle}>
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
    </DashboardCardShell>
  );
}

function InterviewPrepCard({ isOpen, onToggle }: DashboardCardProps) {
  const { data: summary, isLoading } = useInterviewPrepSummary();
  const scopeCount = summary?.scopes.length ?? 0;

  return (
    <DashboardCardShell
      title="Interview Prep"
      description={
        <CardDescription>
          {scopeCount > 0
            ? `Across ${scopeCount} scope${scopeCount === 1 ? "" : "s"}`
            : "Master + every target role"}
        </CardDescription>
      }
      isOpen={isOpen}
      onToggle={onToggle}
    >
      {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
      {!isLoading && scopeCount === 0 && (
        <p className="text-sm text-muted-foreground">
          No articles or questions yet — start building your interview prep.
        </p>
      )}
      {!isLoading &&
        summary?.scopes.map((s) => (
          <div
            key={s.target_role_id ?? "master"}
            className="flex items-center justify-between gap-2 border-b border-border pb-2 last:border-0 last:pb-0"
          >
            <span className="truncate text-sm font-medium">{s.role_name}</span>
            <div className="flex items-center gap-2">
              <Badge variant="default">
                {s.topic_count} {s.topic_count === 1 ? "article" : "articles"}
              </Badge>
              <Badge variant="default">
                {s.question_count} {s.question_count === 1 ? "question" : "questions"}
              </Badge>
            </div>
          </div>
        ))}
      <InlineLink to="/interview-prep" className="text-xs">
        Go to Interview Prep
      </InlineLink>
    </DashboardCardShell>
  );
}
