import {
  useCareerProfile,
  useCareerProfileSummary,
  useClearCareerProfile,
  useTargetRoles,
} from "@/api/queries/career-profile";
import {
  useCancelUpload,
  useDiscardResume,
  useMergeResume,
  useResume,
  useResumeList,
  useUploadResume,
} from "@/api/queries/resume-intelligence";
import type { components } from "@/api/schema.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { OverrideMergeDialog } from "@/components/ui/override-merge-dialog";
import { Select } from "@/components/ui/select";
import { formatDisplayDate, formatDisplayDateTime } from "@/lib/date-format";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { useUploadProgressStore } from "@/stores/upload-progress-store";
import { Trash2, X } from "lucide-react";
import { type ChangeEvent, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

type ResumeResponse = components["schemas"]["ResumeResponse"];
type ResumeSummary = components["schemas"]["ResumeSummary"];
type ExtractedResumeData = components["schemas"]["ExtractedResumeData"];
type ResumeMergeResponse = components["schemas"]["ResumeMergeResponse"];
type CoreCompetency = components["schemas"]["CoreCompetencyPayload"];

const ACCEPTED_TYPES =
  "application/pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

// Must mirror ResumeExtractionService's own limits
// (backend/app/application/resume_intelligence/resume_extraction_service.py)
// — this is a fast-feedback check, not the enforcement boundary; the
// backend still validates independently on every upload regardless of
// what the frontend allowed through.
const MAX_RESUME_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
const MAX_RESUME_SIZE_MB = MAX_RESUME_SIZE_BYTES / (1024 * 1024);

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

/**
 * `file.type` alone is unreliable for .docx across OS/browser
 * combinations (some report a generic octet-stream MIME type), so this
 * also accepts by extension — the same dual check the `accept`
 * attribute below already expresses to the OS file picker.
 */
function validateResumeFile(file: File): string | null {
  const name = file.name.toLowerCase();
  const isPdf = file.type === "application/pdf" || name.endsWith(".pdf");
  const isDocx =
    file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    name.endsWith(".docx");
  if (!isPdf && !isDocx) {
    return "Please choose a PDF or DOCX file.";
  }
  if (file.size > MAX_RESUME_SIZE_BYTES) {
    return `That file is too large — resumes must be under ${MAX_RESUME_SIZE_MB}MB.`;
  }
  return null;
}

/**
 * Top-level Resume Intelligence page (Left Nav item, /resumes) —
 * replaced the old single-slot "upload -> review -> auto-discard" flow
 * (previously reached via a button on the Career Profile page) with a
 * real history: every upload stays listed until the user explicitly
 * deletes it, since a person may keep multiple resume versions, each
 * tailored to a different target role (optionally tagged at upload
 * time). Deleting a resume only removes the resume record — anything
 * already merged from it into the Career Profile stays untouched,
 * matching how the rest of this app treats merged data as independent
 * once written.
 */
export function ResumeIntelligencePage() {
  const { data: resumes, isLoading } = useResumeList();
  const [activeResumeId, setActiveResumeId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ResumeSummary | null>(null);
  const discardResume = useDiscardResume();
  const { data: targetRoles } = useTargetRoles();

  function targetRoleName(id: string | null): string | null {
    if (!id) return null;
    return targetRoles?.find((r) => r.id === id)?.role_name ?? null;
  }

  function handleDelete() {
    if (deleteTarget) {
      discardResume.mutate(deleteTarget.id);
      if (activeResumeId === deleteTarget.id) setActiveResumeId(null);
    }
    setDeleteTarget(null);
  }

  if (activeResumeId) {
    return (
      <ResumeDetailSection resumeId={activeResumeId} onBack={() => setActiveResumeId(null)} />
    );
  }

  return (
    <div className="grid gap-4">
      <div>
        <h2 className="font-display text-lg font-semibold md:text-xl">Resume Intelligence</h2>
        <p className="text-sm text-muted-foreground">
          Upload resumes, review what we extract, and keep multiple versions tailored to
          different target roles.
        </p>
      </div>

      <UploadCard onUploaded={(id) => setActiveResumeId(id)} />

      <Card>
        <CardHeader>
          <CardTitle>Resume History</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}
          {resumes?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No resumes uploaded yet — use the form above to get started.
            </p>
          )}
          {resumes?.map((resume) => (
            <div
              key={resume.id}
              className="flex items-center justify-between gap-4 rounded-md border border-border p-3"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium md:text-base">
                  {resume.original_filename}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <Badge variant={resume.status === "parsed" ? "accent" : "destructive"}>
                    {resume.status === "parsed" ? "Parsed" : "Failed"}
                  </Badge>
                  {targetRoleName(resume.target_role_id) && (
                    <Badge variant="default">{targetRoleName(resume.target_role_id)}</Badge>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {formatDisplayDateTime(resume.created_at)}
                  </span>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <Button variant="outline" size="sm" onClick={() => setActiveResumeId(resume.id)}>
                  {resume.status === "parsed" ? "Review" : "View error"}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(resume)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={deleteTarget !== null}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="Delete this resume?"
        description={
          deleteTarget
            ? `Delete "${deleteTarget.original_filename}"? This only removes the resume record — anything already added to your profile from it stays as-is. This can't be undone.`
            : ""
        }
        isPending={discardResume.isPending}
      />
    </div>
  );
}

function UploadCard({ onUploaded }: { onUploaded: (resumeId: string) => void }) {
  const { data: targetRoles } = useTargetRoles();
  const uploadResume = useUploadResume();
  const cancelUpload = useCancelUpload();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [targetRoleId, setTargetRoleId] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const isUploading = useUploadProgressStore((state) => state.isUploading);
  // Stored globally, not a component-local ref — see upload-progress-store.ts's
  // own docstring for the real bug this fixes: a fresh mount (e.g. the
  // "may still be processing" notice, shown after leaving and returning
  // to this page) has no local ref from whichever earlier mount actually
  // started the upload, so it needs the token to live somewhere that
  // survives the unmount too.
  const uploadToken = useUploadProgressStore((state) => state.uploadToken);
  const startUpload = useUploadProgressStore((state) => state.startUpload);
  const clearUpload = useUploadProgressStore((state) => state.clearUpload);

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // allow re-selecting the same file after a failure
    if (!file) return;

    const message = validateResumeFile(file);
    setValidationError(message);
    if (message) return;

    const controller = new AbortController();
    abortControllerRef.current = controller;
    // A fresh token per attempt is what lets a later handleCancel() call
    // reach exactly THIS attempt's still-running server-side task (see
    // the backend's /upload/{upload_token}/cancel) rather than some
    // earlier or unrelated one.
    const token = crypto.randomUUID();
    // Set BEFORE mutate() (not mirrored from isPending via an effect,
    // and deliberately NOT cleared on unmount) — see handleCancel's own
    // comment for why: once true, this must stay true across a Cancel,
    // and across leaving/returning to this page (a fresh mount gets a
    // fresh, isPending=false mutation instance with no memory of the
    // old one), until a real server response arrives or a confirmed
    // cancel clears it. Clearing it on unmount was the actual gap this
    // exists to close — the button re-enabled itself the moment a user
    // clicked away, even though the server might still be working,
    // inviting exactly the parallel-upload problem this flag exists to
    // prevent — "Choose a resume file" now stays disabled and the
    // notice below stays visible no matter what page the user is on
    // until they cancel or the extraction genuinely finishes.
    startUpload(token);
    uploadResume.mutate(
      { file, targetRoleId: targetRoleId || null, uploadToken: token, signal: controller.signal },
      {
        onSuccess: (data) => {
          clearUpload();
          onUploaded(data.id);
        },
        onError: (error) => {
          // An abort means the BROWSER gave up waiting, not that the
          // server did — per this app's own documented Docker-Desktop
          // networking gotcha, the extraction may well keep running to
          // completion regardless. Only a genuine (non-abort) server
          // response is a definitive enough signal to re-enable
          // uploading; a plain abort (no confirmed cancel) leaves
          // `isUploading` set until handleCancel's cancelUpload call
          // actually confirms the server stopped.
          if (!isAbortError(error)) {
            clearUpload();
          }
        },
      },
    );
  }

  // Two independent actions: abort() gives up on THIS browser tab's own
  // wait for a response, and cancelUpload explicitly tells the backend
  // (by upload_token, see the router's /upload/{upload_token}/cancel)
  // to actually stop the still-running extraction task server-side.
  // Earlier versions of this relied solely on the server detecting the
  // browser's disconnect to decide whether to stop its own work — a
  // real, confirmed-live gotcha: in local dev (Docker Desktop on
  // Windows), that detection reliably failed to fire even on a genuine
  // client disconnect, so the extraction kept running for the full ~10
  // minutes and still wrote its own Resume row once Ollama eventually
  // replied. The explicit cancelUpload call sidesteps that entirely —
  // it's a normal, independent HTTP request the server definitely
  // receives, not something inferred from a dropped connection. Reads
  // the token from the shared store, not a local ref, so this works
  // identically regardless of whether this mount is the one that
  // originally started the upload (see upload-progress-store.ts).
  function handleCancel() {
    abortControllerRef.current?.abort();
    if (!uploadToken) return;
    cancelUpload.mutate(uploadToken, { onSuccess: () => clearUpload() });
  }

  // A local validation failure takes precedence over the previous
  // upload's server-side error, if any — it reflects the file just
  // picked, not whatever happened last time.
  const displayError =
    validationError ??
    (uploadResume.isError && !isAbortError(uploadResume.error)
      ? getErrorMessage(uploadResume.error)
      : null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload New Resume</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-4 text-center">
        {/* Desktop (md:flex): one row — label, dropdown, button, all
            inline. Mobile (the default, plain grid): label+dropdown share
            row 1; the button needs to sit directly below the *dropdown*
            specifically, not below the label at the row's own left edge —
            a plain flex-col stack can't express that (it only has one
            shared left edge), but a 2-column grid does: the button block
            is pinned to `col-start-2`, the same column the dropdown
            occupies, so its left edge lines up with the dropdown's
            regardless of the label's width to its left. `items-center`
            works for both layouts (`align-items` isn't flex-specific), so
            one class pair covers the row-1 label/dropdown centering in
            both modes without needing separate grid/flex variants. */}
        <div className="grid w-full grid-cols-[auto_1fr] items-center gap-x-4 gap-y-3 md:flex md:flex-row md:items-start md:justify-start">
          {targetRoles && targetRoles.length > 0 && (
            <>
              <label htmlFor="resume-target-role" className="whitespace-nowrap text-sm font-medium">
                Target Role (optional):
              </label>
              <Select
                id="resume-target-role"
                className="w-56 justify-self-start"
                value={targetRoleId}
                onChange={(e) => setTargetRoleId(e.target.value)}
              >
                <option value="">General (not tied to a role)</option>
                {targetRoles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.role_name}
                  </option>
                ))}
              </Select>
            </>
          )}
          <div
            className={cn(
              "flex min-w-0 items-start gap-2",
              targetRoles && targetRoles.length > 0 && "col-start-2",
            )}
          >
            <div className="flex min-w-0 flex-col items-center gap-1">
              <Button
                type="button"
                variant="primary"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
              >
                {isUploading ? "Analyzing your resume..." : "Choose a resume file"}
              </Button>
              <p className="text-center text-xs text-muted-foreground">PDF or DOCX, up to 10MB</p>
            </div>
            {isUploading && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleCancel}
                disabled={cancelUpload.isPending}
              >
                <X className="h-4 w-4" />
                {cancelUpload.isPending ? "Cancelling..." : "Cancel"}
              </Button>
            )}
          </div>
        </div>
        {isUploading && (
          <p className="max-w-sm text-center text-sm text-muted-foreground">
            Your resume upload is currently processing in the background. You may cancel it to
            stop the extraction and may "Choose a resume file" right away.
          </p>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_TYPES}
          className="hidden"
          onChange={handleChange}
        />
        {displayError && (
          <p role="alert" className="text-sm text-destructive">
            {displayError}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function ResumeDetailSection({
  resumeId,
  onBack,
}: {
  resumeId: string;
  onBack: () => void;
}) {
  const { data: resume, isLoading } = useResume(resumeId);
  // Scoped to the resume's own target_role_id (null = Master) — this
  // drives the "(already added)" skill-dedup preview below, which must
  // reflect the profile the resume will actually merge into, not always
  // Master. Getting this wrong wouldn't just mis-render a badge: a skill
  // already on the Target Role Profile would show as available to add
  // (misleading, though the merge's own server-side dedup would still
  // catch it), and a Master-only skill would show as "already added" on
  // a Target Role Profile that doesn't actually have it yet, blocking
  // the user from selecting something they should be able to add.
  const { data: profile } = useCareerProfile(resume?.target_role_id ?? null);

  return (
    <div className="grid gap-4">
      <Button type="button" variant="ghost" size="sm" onClick={onBack} className="w-fit">
        ← Back to Resume History
      </Button>

      {isLoading && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            Loading...
          </CardContent>
        </Card>
      )}

      {resume?.status === "failed" && (
        <Card>
          <CardHeader>
            <CardTitle>{resume.original_filename}</CardTitle>
          </CardHeader>
          <CardContent>
            <p role="alert" className="text-sm text-destructive">
              {resume.error_message ?? "Something went wrong reading this file."}
            </p>
          </CardContent>
        </Card>
      )}

      {resume?.status === "parsed" && resume.extracted_data && (
        <ResumeReviewCard
          resume={resume}
          existingSkills={profile?.core_competencies ?? []}
          onBack={onBack}
        />
      )}
    </div>
  );
}

function toggleInSet<T>(current: Set<T>, value: T): Set<T> {
  const next = new Set(current);
  if (next.has(value)) {
    next.delete(value);
  } else {
    next.add(value);
  }
  return next;
}

function ResumeReviewCard({
  resume,
  existingSkills,
  onBack,
}: {
  resume: ResumeResponse;
  existingSkills: CoreCompetency[];
  onBack: () => void;
}) {
  const navigate = useNavigate();
  const mergeResume = useMergeResume();
  // The resume's own tag (set once, at upload time) determines which
  // profile it merges into — Master (null) or that Target Role Profile.
  // Not a choice made here; matches the backend's own resolution in
  // ResumeMergeService.merge().
  const scope = resume.target_role_id;
  const { data: targetRoles } = useTargetRoles();
  const scopeLabel = scope
    ? `the ${targetRoles?.find((r) => r.id === scope)?.role_name ?? "Target Role"} profile`
    : "your Master Profile";
  const { data: summary } = useCareerProfileSummary(scope);
  const clearProfile = useClearCareerProfile(scope);
  const [showOverrideMergeDialog, setShowOverrideMergeDialog] = useState(false);
  // Set only when the merge succeeded but had to skip something (e.g. an
  // experience entry with no usable start date) — held here instead of
  // navigating straight away so that message isn't lost. There's no
  // toast/notification system in this app to fall back on.
  const [mergeResult, setMergeResult] = useState<ResumeMergeResponse | null>(null);

  const raw = resume.extracted_data as ExtractedResumeData;
  const data = {
    headline: raw.headline ?? null,
    summary: raw.summary ?? null,
    skills: raw.skills ?? [],
    experience: raw.experience ?? [],
    education: raw.education ?? [],
    certifications: raw.certifications ?? [],
    careerHighlights: raw.career_highlights ?? [],
    keyAchievements: raw.key_achievements ?? [],
  };
  const existingLower = new Set(existingSkills.map((s) => s.name.toLowerCase()));
  // Selection state is index-based (matches every other section here —
  // selectedExperience/selectedEducation/etc. — and the backend's
  // accepted_skill_indices, which resolves name+category by index
  // straight from the stored extracted_data rather than round-tripping
  // the category back over the wire).
  const newSkillIndices = data.skills.reduce<number[]>((acc, skill, idx) => {
    if (!existingLower.has(skill.name.toLowerCase())) acc.push(idx);
    return acc;
  }, []);

  const [acceptHeadline, setAcceptHeadline] = useState(Boolean(data.headline));
  const [acceptSummary, setAcceptSummary] = useState(Boolean(data.summary));
  const [selectedSkills, setSelectedSkills] = useState<Set<number>>(new Set(newSkillIndices));
  const [selectedExperience, setSelectedExperience] = useState<Set<number>>(
    new Set(data.experience.map((_, i) => i)),
  );
  const [selectedEducation, setSelectedEducation] = useState<Set<number>>(
    new Set(data.education.map((_, i) => i)),
  );
  const [selectedCertifications, setSelectedCertifications] = useState<Set<number>>(
    new Set(data.certifications.map((_, i) => i)),
  );
  const [selectedCareerHighlights, setSelectedCareerHighlights] = useState<Set<number>>(
    new Set(data.careerHighlights.map((_, i) => i)),
  );
  const [selectedKeyAchievements, setSelectedKeyAchievements] = useState<Set<number>>(
    new Set(data.keyAchievements.map((_, i) => i)),
  );

  const nothingSelected =
    !acceptHeadline &&
    !acceptSummary &&
    selectedSkills.size === 0 &&
    selectedExperience.size === 0 &&
    selectedEducation.size === 0 &&
    selectedCertifications.size === 0 &&
    selectedCareerHighlights.size === 0 &&
    selectedKeyAchievements.size === 0;

  function handleMerge() {
    mergeResume.mutate(
      {
        resume_id: resume.id,
        accept_headline: acceptHeadline,
        accept_summary: acceptSummary,
        accepted_skill_indices: Array.from(selectedSkills),
        accepted_experience_indices: Array.from(selectedExperience),
        accepted_education_indices: Array.from(selectedEducation),
        accepted_certification_indices: Array.from(selectedCertifications),
        accepted_career_highlight_indices: Array.from(selectedCareerHighlights),
        accepted_key_achievement_indices: Array.from(selectedKeyAchievements),
      },
      {
        onSuccess: (result) => {
          setShowOverrideMergeDialog(false);
          if ((result.skipped_experience_titles ?? []).length > 0) {
            setMergeResult(result);
          } else {
            navigate(scope ? `/profile?role=${scope}` : "/profile");
          }
        },
      },
    );
  }

  // Uploads should never silently blend into old data — if the
  // destination profile already has anything, ask Override vs Merge
  // instead of merging straight away. Both paths still run the same
  // deduped merge(); Override just clears the destination first so the
  // merge lands on a clean slate.
  function handleMergeButtonClick() {
    if (summary?.has_any_data) {
      setShowOverrideMergeDialog(true);
    } else {
      handleMerge();
    }
  }

  async function handleOverrideAndMerge() {
    await clearProfile.mutateAsync();
    handleMerge();
  }

  if (mergeResult) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Added to your profile</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            {mergeResult.added_experience_count} experience,{" "}
            {mergeResult.added_education_count} education,{" "}
            {mergeResult.added_certification_count} certification,{" "}
            {mergeResult.added_career_highlight_count} career highlight,{" "}
            {mergeResult.added_key_achievement_count} key achievement, and{" "}
            {mergeResult.added_skills_count} skill entr
            {mergeResult.added_skills_count === 1 ? "y" : "ies"} added.
          </p>
          <div className="rounded-md border border-border bg-muted p-3">
            <p className="text-sm font-medium">
              Couldn't add automatically — no start date was found for:
            </p>
            <ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">
              {(mergeResult.skipped_experience_titles ?? []).map((title) => (
                <li key={title}>{title}</li>
              ))}
            </ul>
            <p className="mt-2 text-sm text-muted-foreground">
              Add these manually from the Professional Experience section.
            </p>
          </div>
          <Button type="button" variant="primary" onClick={() => navigate("/profile")}>
            Go to Career Profile
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Review extracted from "{resume.original_filename}"</CardTitle>
        <p className="text-sm text-muted-foreground">
          Uncheck anything you don't want added, then add the rest to your profile.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {data.headline && (
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-border"
              checked={acceptHeadline}
              onChange={() => setAcceptHeadline((prev) => !prev)}
            />
            <span>
              <span className="font-medium">Headline: </span>
              {data.headline}
            </span>
          </label>
        )}

        {data.summary && (
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-border"
              checked={acceptSummary}
              onChange={() => setAcceptSummary((prev) => !prev)}
            />
            <span>
              <span className="font-medium">Summary: </span>
              {data.summary}
            </span>
          </label>
        )}

        {data.skills.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium">Skills</p>
            <div className="flex flex-wrap gap-1.5">
              {data.skills.map((skill, idx) => {
                const alreadyOwned = existingLower.has(skill.name.toLowerCase());
                const selected = selectedSkills.has(idx);
                const title = alreadyOwned
                  ? "Already in your profile"
                  : skill.category
                    ? `Category: ${skill.category}`
                    : undefined;
                return (
                  <button
                    type="button"
                    key={idx}
                    disabled={alreadyOwned}
                    onClick={() => setSelectedSkills((prev) => toggleInSet(prev, idx))}
                    title={title}
                  >
                    <Badge
                      variant={alreadyOwned ? "default" : selected ? "accent" : "default"}
                      className={alreadyOwned ? "opacity-60" : undefined}
                    >
                      {skill.name}
                      {alreadyOwned ? " (already added)" : ""}
                    </Badge>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {data.experience.length > 0 && (
          <ReviewList
            title="Experience"
            items={data.experience}
            selected={selectedExperience}
            onToggle={(i) => setSelectedExperience((prev) => toggleInSet(prev, i))}
            renderItem={(item) => (
              <>
                <p className="text-sm font-medium md:text-base">{item.title}</p>
                <p className="text-sm text-muted-foreground">{item.company}</p>
                <p className="text-xs font-bold italic text-accent">
                  {formatDisplayDate(item.start_date)} –{" "}
                  {item.end_date ? formatDisplayDate(item.end_date) : "Present"}
                </p>
              </>
            )}
          />
        )}

        {data.education.length > 0 && (
          <ReviewList
            title="Education"
            items={data.education}
            selected={selectedEducation}
            onToggle={(i) => setSelectedEducation((prev) => toggleInSet(prev, i))}
            renderItem={(item) => (
              <>
                <p className="text-sm font-medium md:text-base">{item.institution}</p>
                {item.degree && <p className="text-sm text-muted-foreground">{item.degree}</p>}
              </>
            )}
          />
        )}

        {data.certifications.length > 0 && (
          <ReviewList
            title="Certifications"
            items={data.certifications}
            selected={selectedCertifications}
            onToggle={(i) => setSelectedCertifications((prev) => toggleInSet(prev, i))}
            renderItem={(item) => (
              <>
                <p className="text-sm font-medium md:text-base">{item.name}</p>
                <p className="text-sm text-muted-foreground">{item.issuing_organization}</p>
              </>
            )}
          />
        )}

        {data.careerHighlights.length > 0 && (
          <ReviewList
            title="Career Highlights"
            items={data.careerHighlights}
            selected={selectedCareerHighlights}
            onToggle={(i) => setSelectedCareerHighlights((prev) => toggleInSet(prev, i))}
            renderItem={(item) => (
              <>
                <p className="text-sm font-medium md:text-base">{item.title}</p>
                {item.company && (
                  <p className="text-sm text-muted-foreground">{item.company}</p>
                )}
              </>
            )}
          />
        )}

        {data.keyAchievements.length > 0 && (
          <ReviewList
            title="Key Achievements"
            items={data.keyAchievements}
            selected={selectedKeyAchievements}
            onToggle={(i) => setSelectedKeyAchievements((prev) => toggleInSet(prev, i))}
            renderItem={(item) => (
              <>
                <p className="text-sm font-medium md:text-base">{item.title}</p>
                {item.company && (
                  <p className="text-sm text-muted-foreground">{item.company}</p>
                )}
              </>
            )}
          />
        )}

        {mergeResume.isError && (
          <p role="alert" className="text-sm text-destructive">
            {getErrorMessage(mergeResume.error)}
          </p>
        )}

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="primary"
            onClick={handleMergeButtonClick}
            disabled={mergeResume.isPending || clearProfile.isPending || nothingSelected}
          >
            {mergeResume.isPending || clearProfile.isPending ? "Adding..." : "Add Selected to Profile"}
          </Button>
          <Button type="button" variant="ghost" onClick={onBack} disabled={mergeResume.isPending}>
            Back to Resume History
          </Button>
        </div>
      </CardContent>

      <OverrideMergeDialog
        open={showOverrideMergeDialog}
        onCancel={() => setShowOverrideMergeDialog(false)}
        onMerge={handleMerge}
        onOverride={handleOverrideAndMerge}
        scopeLabel={scopeLabel}
        summary={summary}
        isMerging={mergeResume.isPending}
        isOverriding={clearProfile.isPending}
      />
    </Card>
  );
}

function ReviewList<T>({
  title,
  items,
  selected,
  onToggle,
  renderItem,
}: {
  title: string;
  items: T[];
  selected: Set<number>;
  onToggle: (index: number) => void;
  renderItem: (item: T) => React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium">{title}</p>
      <div className="flex flex-col gap-2">
        {items.map((item, index) => (
          <label
            key={index}
            className="flex items-start gap-3 rounded-md border border-border p-3"
          >
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 shrink-0 rounded border-border"
              checked={selected.has(index)}
              onChange={() => onToggle(index)}
            />
            <div className="min-w-0 flex-1">{renderItem(item)}</div>
          </label>
        ))}
      </div>
    </div>
  );
}
