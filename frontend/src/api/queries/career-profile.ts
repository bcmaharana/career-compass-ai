import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type CareerProfileResponse = components["schemas"]["CareerProfileResponse"];
type UpdateCareerProfileRequest = components["schemas"]["UpdateCareerProfileRequest"];
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

const KEYS = {
  profile: ["career-profile"],
  experiences: ["career-profile", "experiences"],
  educations: ["career-profile", "educations"],
  certifications: ["career-profile", "certifications"],
  goals: ["career-goals"],
  highlights: ["career-profile", "highlights"],
  achievements: ["career-profile", "achievements"],
  endorsements: ["career-profile", "endorsements"],
  targetRoles: ["career-profile", "target-roles"],
} as const;

export function useCareerProfile() {
  return useQuery({
    queryKey: KEYS.profile,
    queryFn: () => apiClient.get<CareerProfileResponse>("/api/v1/career-profile"),
  });
}

export function useUpdateCareerProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateCareerProfileRequest) =>
      apiClient.patch<CareerProfileResponse>("/api/v1/career-profile", body),
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
      queryClient.setQueryData(KEYS.profile, data);
      await queryClient.refetchQueries({ queryKey: KEYS.profile });
      // core_competencies feeds Gap Analysis (My Skills owned-skill set) —
      // invalidate on every profile update rather than threading a
      // "did core_competencies change" flag through every call site.
      queryClient.invalidateQueries({ queryKey: ["skills", "gap-analysis"] });
    },
  });
}

export function useExperiences() {
  return useQuery({
    queryKey: KEYS.experiences,
    queryFn: () => apiClient.get<ExperienceResponse[]>("/api/v1/career-profile/experiences"),
  });
}

export function useAddExperience() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ExperienceRequest) =>
      apiClient.post<ExperienceResponse>("/api/v1/career-profile/experiences", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.experiences }),
  });
}

export function useUpdateExperience() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ExperienceRequest }) =>
      apiClient.patch<ExperienceResponse>(`/api/v1/career-profile/experiences/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.experiences }),
  });
}

export function useDeleteExperience() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/experiences/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.experiences }),
  });
}

export function useEducations() {
  return useQuery({
    queryKey: KEYS.educations,
    queryFn: () => apiClient.get<EducationResponse[]>("/api/v1/career-profile/educations"),
  });
}

export function useAddEducation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: EducationRequest) =>
      apiClient.post<EducationResponse>("/api/v1/career-profile/educations", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.educations }),
  });
}

export function useUpdateEducation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: EducationRequest }) =>
      apiClient.patch<EducationResponse>(`/api/v1/career-profile/educations/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.educations }),
  });
}

export function useDeleteEducation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/educations/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.educations }),
  });
}

export function useCertifications() {
  return useQuery({
    queryKey: KEYS.certifications,
    queryFn: () =>
      apiClient.get<CertificationResponse[]>("/api/v1/career-profile/certifications"),
  });
}

export function useAddCertification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CertificationRequest) =>
      apiClient.post<CertificationResponse>("/api/v1/career-profile/certifications", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.certifications }),
  });
}

export function useUpdateCertification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CertificationRequest }) =>
      apiClient.patch<CertificationResponse>(`/api/v1/career-profile/certifications/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.certifications }),
  });
}

export function useDeleteCertification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/certifications/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.certifications }),
  });
}

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

export function useUploadProfilePhoto() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) =>
      apiClient.uploadFile<PhotoUploadResponse>("/api/v1/career-profile/photo", file),
    // Merges into the existing cached profile rather than invalidating
    // (which would trigger a background refetch) — see ProfileHeader's
    // docstring for why a refetch racing against an in-progress, unsaved
    // edit elsewhere on the same form was a real bug, not a theoretical one.
    onSuccess: (data) =>
      queryClient.setQueryData(
        KEYS.profile,
        (old: CareerProfileResponse | undefined) =>
          old && { ...old, photo_url: data.photo_url },
      ),
  });
}

export function useCareerHighlights() {
  return useQuery({
    queryKey: KEYS.highlights,
    queryFn: () => apiClient.get<CareerHighlightResponse[]>("/api/v1/career-profile/highlights"),
  });
}

export function useAddCareerHighlight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CareerHighlightRequest) =>
      apiClient.post<CareerHighlightResponse>("/api/v1/career-profile/highlights", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.highlights }),
  });
}

export function useUpdateCareerHighlight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CareerHighlightRequest }) =>
      apiClient.patch<CareerHighlightResponse>(`/api/v1/career-profile/highlights/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.highlights }),
  });
}

export function useDeleteCareerHighlight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/highlights/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.highlights }),
  });
}

export function useKeyAchievements() {
  return useQuery({
    queryKey: KEYS.achievements,
    queryFn: () => apiClient.get<KeyAchievementResponse[]>("/api/v1/career-profile/achievements"),
  });
}

export function useAddKeyAchievement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: KeyAchievementRequest) =>
      apiClient.post<KeyAchievementResponse>("/api/v1/career-profile/achievements", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.achievements }),
  });
}

export function useUpdateKeyAchievement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: KeyAchievementRequest }) =>
      apiClient.patch<KeyAchievementResponse>(`/api/v1/career-profile/achievements/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.achievements }),
  });
}

export function useDeleteKeyAchievement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/achievements/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.achievements }),
  });
}

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

// --- Reordering ---
// Every move endpoint returns the full, freshly-ordered list, so the
// mutation writes it straight into the cache (setQueryData) rather than
// invalidating and waiting on a separate refetch — reordering should
// feel instant.

export function useMoveExperience() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<ExperienceResponse[]>(`/api/v1/career-profile/experiences/${id}/move`, {
        direction,
      }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.experiences, data),
  });
}

export function useMoveEducation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<EducationResponse[]>(`/api/v1/career-profile/educations/${id}/move`, {
        direction,
      }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.educations, data),
  });
}

export function useMoveCertification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<CertificationResponse[]>(`/api/v1/career-profile/certifications/${id}/move`, {
        direction,
      }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.certifications, data),
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

export function useMoveCareerHighlight() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<CareerHighlightResponse[]>(`/api/v1/career-profile/highlights/${id}/move`, {
        direction,
      }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.highlights, data),
  });
}

export function useMoveKeyAchievement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, direction }: { id: string; direction: MoveDirection }) =>
      apiClient.post<KeyAchievementResponse[]>(`/api/v1/career-profile/achievements/${id}/move`, {
        direction,
      }),
    onSuccess: (data) => queryClient.setQueryData(KEYS.achievements, data),
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
