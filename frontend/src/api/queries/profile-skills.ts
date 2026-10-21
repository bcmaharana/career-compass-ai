import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type ProfileSkill = components["schemas"]["ProfileSkillResponse"] & {
  skill_file_name?: string | null;
  skill_file_content_type?: string | null;
  badge_image_name?: string | null;
  badge_url?: string | null;
  share_key?: string | null;
};

export type ProfileSkillRequest = components["schemas"]["ProfileSkillRequest"] & {
  badge_url?: string | null;
};

export interface PublicProfileSkill {
  owner_display_name: string;
  name: string;
  issuing_organization: string;
  issue_date: string | null;
  expiration_date: string | null;
  credential_id: string | null;
  credential_url: string | null;
  skill_file_name: string | null;
  skill_file_content_type: string | null;
  skill_file_url: string | null;
  badge_image_url: string | null;
  badge_url: string | null;
}

const PROFILE_SKILL_QUERY_KEY = ["career-profile", "skills", "master"] as const;

export function useProfileSkills() {
  return useQuery({
    queryKey: PROFILE_SKILL_QUERY_KEY,
    queryFn: () => apiClient.get<ProfileSkill[]>("/api/v1/career-profile/skills"),
  });
}

export function useAddProfileSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileSkillRequest) =>
      apiClient.post<ProfileSkill>("/api/v1/career-profile/skills", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROFILE_SKILL_QUERY_KEY }),
  });
}

export function useUpdateProfileSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ProfileSkillRequest }) =>
      apiClient.patch<ProfileSkill>(`/api/v1/career-profile/skills/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROFILE_SKILL_QUERY_KEY }),
  });
}

export function useDeleteProfileSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/skills/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROFILE_SKILL_QUERY_KEY }),
  });
}

export function useUploadProfileSkillFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, kind, file }: { id: string; kind: "skill" | "badge"; file: File }) =>
      apiClient.uploadFile<ProfileSkill>(
        `/api/v1/career-profile/skills/${id}/files/${kind}`,
        file,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROFILE_SKILL_QUERY_KEY }),
  });
}

export function useDeleteProfileSkillFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, kind }: { id: string; kind: "skill" | "badge" }) =>
      apiClient.delete(`/api/v1/career-profile/skills/${id}/files/${kind}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROFILE_SKILL_QUERY_KEY }),
  });
}

export function useProfileSkillFileUrl() {
  return useMutation({
    mutationFn: ({ id, kind }: { id: string; kind: "skill" | "badge" }) =>
      apiClient.get<{ url: string }>(`/api/v1/career-profile/skills/${id}/files/${kind}`),
  });
}

export function useShareProfileSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.post<{ share_key: string }>(`/api/v1/career-profile/skills/${id}/share`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROFILE_SKILL_QUERY_KEY }),
  });
}

export function useRevokeProfileSkillShare() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/skills/${id}/share`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: PROFILE_SKILL_QUERY_KEY }),
  });
}

export function usePublicProfileSkill(shareKey: string | undefined) {
  return useQuery({
    queryKey: ["public-profile-skill", shareKey],
    queryFn: () => apiClient.get<PublicProfileSkill>(`/api/v1/public/skills/${shareKey}`),
    enabled: !!shareKey,
    retry: false,
  });
}
