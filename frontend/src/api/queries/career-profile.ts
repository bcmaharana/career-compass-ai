import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type CareerProfileResponse = components["schemas"]["CareerProfileResponse"];
type UpdateCareerProfileRequest = components["schemas"]["UpdateCareerProfileRequest"];
type GenerateResumeRequest = components["schemas"]["GenerateResumeRequest"];
type CareerProfileSummaryResponse = components["schemas"]["CareerProfileSummaryResponse"];
type PhotoUploadResponse = components["schemas"]["PhotoUploadResponse"];

type ExperienceResponse = components["schemas"]["ExperienceResponse"];
type ExperienceRequest = components["schemas"]["ExperienceRequest"];

type EducationResponse = components["schemas"]["EducationResponse"];
type EducationRequest = components["schemas"]["EducationRequest"];

type CertificationResponse = components["schemas"]["CertificationResponse"];
type CertificationRequest = components["schemas"]["CertificationRequest"];

type CareerGoalResponse = components["schemas"]["CareerGoalResponse"];
type CareerGoalRequest = components["schemas"]["CareerGoalRequest"];
type CareerGoalUpdateRequest = components["schemas"]["CareerGoalUpdateRequest"];

type CareerHighlightResponse = components["schemas"]["CareerHighlightResponse"];
type CareerHighlightRequest = components["schemas"]["CareerHighlightRequest"];

type KeyAchievementResponse = components["schemas"]["KeyAchievementResponse"];
type KeyAchievementRequest = components["schemas"]["KeyAchievementRequest"];

type PeerEndorsementResponse = components["schemas"]["PeerEndorsementResponse"];
type PeerEndorsementRequest = components["schemas"]["PeerEndorsementRequest"];

type TargetRoleResponse = components["schemas"]["TargetRoleResponse"];
type TargetRoleRequest = components["schemas"]["TargetRoleRequest"];

type MoveDirection = "up" | "down";

/** null = Master Profile, a real id = that Target Role Profile — the
 * single scoping axis threaded through every profile/experience/
 * education/certification/highlight/achievement query below. Career
 * Goals, Peer Endorsements, and Target Role CRUD itself stay unscoped
 * (Master-only), per the Master/Target-Role-Profile design. */
type Scope = string | null;

function scopeKey(scope: Scope): string {
  return scope ?? "master";
}

/** Appends `?target_role_id=` when scoped — every list/add/clear/summary
 * endpoint below accepts this as an optional query param; a plain id
 * (not further encoded) is safe here since target role ids are UUIDs. */
function withScope(path: string, scope: Scope): string {
  return scope ? `${path}?target_role_id=${scope}` : path;
}

const KEYS = {
  profile: (scope: Scope) => ["career-profile", scopeKey(scope)] as const,
  summary: (scope: Scope) => ["career-profile", "summary", scopeKey(scope)] as const,
  experiences: (scope: Scope) => ["career-profile", "experiences", scopeKey(scope)] as const,
  educations: (scope: Scope) => ["career-profile", "educations", scopeKey(scope)] as const,
  certifications: (scope: Scope) => ["career-profile", "certifications", scopeKey(scope)] as const,
  highlights: (scope: Scope) => ["career-profile", "highlights", scopeKey(scope)] as const,
  achievements: (scope: Scope) => ["career-profile", "achievements", scopeKey(scope)] as const,
  // Master-only — no scope axis.
  goals: ["career-goals"],
  endorsements: ["career-profile", "endorsements"],
  targetRoles: ["career-profile", "target-roles"],
} as const;

export function useCareerProfile(scope: Scope = null) {
  return useQuery({
    queryKey: KEYS.profile(scope),
    queryFn: () => apiClient.get<CareerProfileResponse>(withScope("/api/v1/career-profile", scope)),
  });
}

/** Cheap counts snapshot of one profile — powers the Override-vs-Merge
 * prompt during resume merge (see resume-intelligence.ts's useMergeResume
 * caller), so the choice is informed rather than a content-free yes/no. */
export function useCareerProfileSummary(scope: Scope, enabled = true) {
  return useQuery({
    queryKey: KEYS.summary(scope),
    queryFn: () =>
      apiClient.get<CareerProfileSummaryResponse>(withScope("/api/v1/career-profile/summary", scope)),
    enabled,
  });
}

export function useUpdateCareerProfile(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateCareerProfileRequest) =>
      apiClient.patch<CareerProfileResponse>(withScope("/api/v1/career-profile", scope), body),
    // Writes the confirmed server response straight into the cache
    // (instant UI update), then also triggers a real refetch as a
    // belt-and-suspenders check that what's displayed genuinely matches
    // what the server has — cheap, and eliminates any remaining doubt
    // about the two ever disagreeing. This refetch is only safe to add
    // now that ProfileHeader's edit-form fields are no longer reactively
    // re-synced from this query on every change (see ProfileHeader.tsx) —
    // earlier, a refetch landing while the form was open could silently
    // overwrite an unsaved edit; now the form only reads from the query
    // once, explicitly, when Edit is clicked.
    onSuccess: async (data) => {
      queryClient.setQueryData(KEYS.profile(scope), data);
      await queryClient.refetchQueries({ queryKey: KEYS.profile(scope) });
      // core_competencies feeds Gap Analysis (My Skills owned-skill set) —
      // invalidate on every profile update rather than threading a
      // "did core_competencies change" flag through every call site.
      queryClient.invalidateQueries({ queryKey: ["skills", "gap-analysis"] });
    },
  });
}

/** Generates (or regenerates — overwrites, doesn't accumulate a
 * history) a downloadable resume document for this profile. The
 * response carries a fresh presigned resume_docx_url/resume_pdf_url
 * (see backend ResumeExportService) — the caller triggers the actual
 * browser download by navigating to whichever one matches the format
 * just requested. */
export function useGenerateResume(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: GenerateResumeRequest) =>
      apiClient.post<CareerProfileResponse>(
        withScope("/api/v1/career-profile/resume-export", scope),
        body,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(KEYS.profile(scope), data);
    },
  });
}

/** Clears every section this profile owns. Scoped to Master by default
 * (unchanged behavior); a Target Role Profile's clear skips Career
 * Goals/Peer Endorsements/photo, which stay Master-only regardless of
 * scope — see clear_profile_service.py's own scoped-vs-unscoped split. */
export function useClearCareerProfile(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.delete<void>(withScope("/api/v1/career-profile", scope)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.profile(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.experiences(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.educations(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.certifications(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.highlights(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.achievements(scope) });
      if (scope === null) {
        queryClient.invalidateQueries({ queryKey: KEYS.goals });
        queryClient.invalidateQueries({ queryKey: KEYS.endorsements });
      }
      queryClient.invalidateQueries({ queryKey: ["skills", "gap-analysis"] });
    },
  });
}

export function useDeleteProfilePhoto() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.delete<void>("/api/v1/career-profile/photo"),
    // Photo is always Master's, regardless of which profile is currently
    // being viewed — always writes into the Master (null-scope) cache.
    onSuccess: () =>
      queryClient.setQueryData(
        KEYS.profile(null),
        (old: CareerProfileResponse | undefined) => old && { ...old, photo_url: null },
      ),
  });
}

export function useExperiences(scope: Scope = null) {
  return useQuery({
    queryKey: KEYS.experiences(scope),
    queryFn: () =>
      apiClient.get<ExperienceResponse[]>(withScope("/api/v1/career-profile/experiences", scope)),
  });
}

export function useAddExperience(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ExperienceRequest) =>
      apiClient.post<ExperienceResponse>(withScope("/api/v1/career-profile/experiences", scope), body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.experiences(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

// Single-item update/delete resolve ownership from the item's own
// career_profile_id server-side (no target_role_id needed on the
// request) — but the cache key to invalidate still depends on which
// scope the caller is currently viewing, so `scope` here is purely a
// cache-invalidation hint, never sent to the backend.
export function useUpdateExperience(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ExperienceRequest }) =>
      apiClient.patch<ExperienceResponse>(`/api/v1/career-profile/experiences/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.experiences(scope) }),
  });
}

export function useDeleteExperience(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/experiences/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.experiences(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useClearExperiences(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.delete<void>(withScope("/api/v1/career-profile/experiences", scope)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.experiences(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useEducations(scope: Scope = null) {
  return useQuery({
    queryKey: KEYS.educations(scope),
    queryFn: () =>
      apiClient.get<EducationResponse[]>(withScope("/api/v1/career-profile/educations", scope)),
  });
}

export function useAddEducation(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: EducationRequest) =>
      apiClient.post<EducationResponse>(withScope("/api/v1/career-profile/educations", scope), body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.educations(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useUpdateEducation(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: EducationRequest }) =>
      apiClient.patch<EducationResponse>(`/api/v1/career-profile/educations/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.educations(scope) }),
  });
}

export function useDeleteEducation(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/educations/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.educations(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useClearEducations(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.delete<void>(withScope("/api/v1/career-profile/educations", scope)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.educations(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useCertifications(scope: Scope = null) {
  return useQuery({
    queryKey: KEYS.certifications(scope),
    queryFn: () =>
      apiClient.get<CertificationResponse[]>(
        withScope("/api/v1/career-profile/certifications", scope),
      ),
  });
}

export function useAddCertification(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CertificationRequest) =>
      apiClient.post<CertificationResponse>(
        withScope("/api/v1/career-profile/certifications", scope),
        body,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.certifications(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useUpdateCertification(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CertificationRequest }) =>
      apiClient.patch<CertificationResponse>(`/api/v1/career-profile/certifications/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.certifications(scope) }),
  });
}

export function useDeleteCertification(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/certifications/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.certifications(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useClearCertifications(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.delete<void>(withScope("/api/v1/career-profile/certifications", scope)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.certifications(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

// --- Career Goals — Master-only, no scope axis (not part of resume
// extraction/merge, no clear use case yet for per-target-role goals). ---

export function useCareerGoals() {
  return useQuery({
    queryKey: KEYS.goals,
    queryFn: () => apiClient.get<CareerGoalResponse[]>("/api/v1/career-goals"),
  });
}

export function useAddCareerGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CareerGoalRequest) =>
      apiClient.post<CareerGoalResponse>("/api/v1/career-goals", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.goals }),
  });
}

export function useUpdateCareerGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CareerGoalUpdateRequest }) =>
      apiClient.patch<CareerGoalResponse>(`/api/v1/career-goals/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.goals }),
  });
}

export function useDeleteCareerGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-goals/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.goals }),
  });
}

export function useClearCareerGoals() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.delete<void>("/api/v1/career-goals"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.goals }),
  });
}

export function useUploadProfilePhoto() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) =>
      apiClient.uploadFile<PhotoUploadResponse>("/api/v1/career-profile/photo", file),
    // Merges into the existing cached profile rather than invalidating
    // (which would trigger a background refetch) — see ProfileHeader's
    // docstring for why a refetch racing against an in-progress, unsaved
    // edit elsewhere on the same form was a real bug, not a theoretical one.
    // Always Master's photo, regardless of the currently-viewed scope.
    onSuccess: (data) =>
      queryClient.setQueryData(
        KEYS.profile(null),
        (old: CareerProfileResponse | undefined) =>
          old && { ...old, photo_url: data.photo_url },
      ),
  });
}

export function useCareerHighlights(scope: Scope = null) {
  return useQuery({
    queryKey: KEYS.highlights(scope),
    queryFn: () =>
      apiClient.get<CareerHighlightResponse[]>(
        withScope("/api/v1/career-profile/highlights", scope),
      ),
  });
}

export function useAddCareerHighlight(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CareerHighlightRequest) =>
      apiClient.post<CareerHighlightResponse>(
        withScope("/api/v1/career-profile/highlights", scope),
        body,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.highlights(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useUpdateCareerHighlight(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CareerHighlightRequest }) =>
      apiClient.patch<CareerHighlightResponse>(`/api/v1/career-profile/highlights/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.highlights(scope) }),
  });
}

export function useDeleteCareerHighlight(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/highlights/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.highlights(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useClearCareerHighlights(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.delete<void>(withScope("/api/v1/career-profile/highlights", scope)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.highlights(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useKeyAchievements(scope: Scope = null) {
  return useQuery({
    queryKey: KEYS.achievements(scope),
    queryFn: () =>
      apiClient.get<KeyAchievementResponse[]>(
        withScope("/api/v1/career-profile/achievements", scope),
      ),
  });
}

export function useAddKeyAchievement(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: KeyAchievementRequest) =>
      apiClient.post<KeyAchievementResponse>(
        withScope("/api/v1/career-profile/achievements", scope),
        body,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.achievements(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useUpdateKeyAchievement(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: KeyAchievementRequest }) =>
      apiClient.patch<KeyAchievementResponse>(`/api/v1/career-profile/achievements/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.achievements(scope) }),
  });
}

export function useDeleteKeyAchievement(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/achievements/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.achievements(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

export function useClearKeyAchievements(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.delete<void>(withScope("/api/v1/career-profile/achievements", scope)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEYS.achievements(scope) });
      queryClient.invalidateQueries({ queryKey: KEYS.summary(scope) });
    },
  });
}

// --- Peer Endorsements — Master-only, no scope axis. ---

export function usePeerEndorsements() {
  return useQuery({
    queryKey: KEYS.endorsements,
    queryFn: () =>
      apiClient.get<PeerEndorsementResponse[]>("/api/v1/career-profile/endorsements"),
  });
}

export function useAddPeerEndorsement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PeerEndorsementRequest) =>
      apiClient.post<PeerEndorsementResponse>("/api/v1/career-profile/endorsements", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.endorsements }),
  });
}

export function useUpdatePeerEndorsement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: PeerEndorsementRequest }) =>
      apiClient.patch<PeerEndorsementResponse>(`/api/v1/career-profile/endorsements/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.endorsements }),
  });
}

export function useDeletePeerEndorsement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/endorsements/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.endorsements }),
  });
}

export function useClearPeerEndorsements() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.delete<void>("/api/v1/career-profile/endorsements"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.endorsements }),
  });
}

// --- Reordering ---
// Every move endpoint returns the full, freshly-ordered list for the
// requested scope, so the mutation writes it straight into the cache
// (setQueryData) rather than invalidating and waiting on a separate
// refetch — reordering should feel instant. `scope` is passed as a query
// param purely so the backend knows which list to hand back — the move
// itself resolves ownership from the item's own career_profile_id.

export function useMoveExperience(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<ExperienceResponse[]>(
        withScope(`/api/v1/career-profile/experiences/${id}/move`, scope),
        { direction },
      ),
    onSuccess: (data) => queryClient.setQueryData(KEYS.experiences(scope), data),
  });
}

export function useMoveEducation(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<EducationResponse[]>(
        withScope(`/api/v1/career-profile/educations/${id}/move`, scope),
        { direction },
      ),
    onSuccess: (data) => queryClient.setQueryData(KEYS.educations(scope), data),
  });
}

export function useMoveCertification(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<CertificationResponse[]>(
        withScope(`/api/v1/career-profile/certifications/${id}/move`, scope),
        { direction },
      ),
    onSuccess: (data) => queryClient.setQueryData(KEYS.certifications(scope), data),
  });
}

export function useMoveCareerGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<CareerGoalResponse[]>(`/api/v1/career-goals/${id}/move`, { direction }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.goals, data),
  });
}

export function useMoveCareerHighlight(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<CareerHighlightResponse[]>(
        withScope(`/api/v1/career-profile/highlights/${id}/move`, scope),
        { direction },
      ),
    onSuccess: (data) => queryClient.setQueryData(KEYS.highlights(scope), data),
  });
}

export function useMoveKeyAchievement(scope: Scope = null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<KeyAchievementResponse[]>(
        withScope(`/api/v1/career-profile/achievements/${id}/move`, scope),
        { direction },
      ),
    onSuccess: (data) => queryClient.setQueryData(KEYS.achievements(scope), data),
  });
}

export function useMovePeerEndorsement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<PeerEndorsementResponse[]>(`/api/v1/career-profile/endorsements/${id}/move`, {
        direction,
      }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.endorsements, data),
  });
}

// --- Target Roles — the scoping dimension itself, always unscoped. ---

export function useTargetRoles() {
  return useQuery({
    queryKey: KEYS.targetRoles,
    queryFn: () => apiClient.get<TargetRoleResponse[]>("/api/v1/career-profile/target-roles"),
  });
}

export function useAddTargetRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TargetRoleRequest) =>
      apiClient.post<TargetRoleResponse>("/api/v1/career-profile/target-roles", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.targetRoles }),
  });
}

export function useUpdateTargetRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: TargetRoleRequest }) =>
      apiClient.patch<TargetRoleResponse>(`/api/v1/career-profile/target-roles/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.targetRoles }),
  });
}

export function useDeleteTargetRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/target-roles/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.targetRoles }),
  });
}

function replaceTargetRoleInCache(
  queryClient: ReturnType<typeof useQueryClient>,
  updated: TargetRoleResponse,
) {
  queryClient.setQueryData(KEYS.targetRoles, (old: TargetRoleResponse[] | undefined) =>
    old?.map((role) => (role.id === updated.id ? updated : role)),
  );
}

export function useAddRequiredSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ targetRoleId, name }: { targetRoleId: string; name: string }) =>
      apiClient.post<TargetRoleResponse>(
        `/api/v1/career-profile/target-roles/${targetRoleId}/required-skills`,
        { name },
      ),
    onSuccess: (data) => {
      replaceTargetRoleInCache(queryClient, data);
      queryClient.invalidateQueries({ queryKey: ["skills", "gap-analysis"] });
    },
  });
}

export function useRemoveRequiredSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ targetRoleId, name }: { targetRoleId: string; name: string }) =>
      apiClient.delete<TargetRoleResponse>(
        `/api/v1/career-profile/target-roles/${targetRoleId}/required-skills/${encodeURIComponent(name)}`,
      ),
    onSuccess: (data) => {
      replaceTargetRoleInCache(queryClient, data);
      queryClient.invalidateQueries({ queryKey: ["skills", "gap-analysis"] });
    },
  });
}

export function useRenameRequiredSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      targetRoleId,
      oldName,
      newName,
    }: {
      targetRoleId: string;
      oldName: string;
      newName: string;
    }) =>
      apiClient.patch<TargetRoleResponse>(
        `/api/v1/career-profile/target-roles/${targetRoleId}/required-skills/${encodeURIComponent(oldName)}`,
        { name: newName },
      ),
    onSuccess: (data) => {
      replaceTargetRoleInCache(queryClient, data);
      queryClient.invalidateQueries({ queryKey: ["skills", "gap-analysis"] });
    },
  });
}
