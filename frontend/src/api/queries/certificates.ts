import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type Certificate =
  components["schemas"]["CertificationResponse"] & {
    certificate_file_name?: string | null;
    certificate_file_content_type?: string | null;
    badge_image_name?: string | null;
    badge_url?: string | null;
    share_key?: string | null;
  };

export type CertificateRequest = components["schemas"]["CertificationRequest"] & {
  badge_url?: string | null;
};

export interface PublicCertificate {
  owner_display_name: string;
  name: string;
  issuing_organization: string;
  issue_date: string | null;
  expiration_date: string | null;
  does_not_expire: boolean;
  credential_id: string | null;
  credential_url: string | null;
  certificate_file_name: string | null;
  certificate_file_content_type: string | null;
  certificate_file_url: string | null;
  badge_image_url: string | null;
  badge_url: string | null;
}

const CERTIFICATE_QUERY_KEY = ["career-profile", "certifications", "master"] as const;

export function useAddCertificate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CertificateRequest) =>
      apiClient.post<Certificate>("/api/v1/career-profile/certifications", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CERTIFICATE_QUERY_KEY }),
  });
}

export function useUpdateCertificate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CertificateRequest }) =>
      apiClient.patch<Certificate>(`/api/v1/career-profile/certifications/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CERTIFICATE_QUERY_KEY }),
  });
}

export function useDeleteCertificate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/v1/career-profile/certifications/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CERTIFICATE_QUERY_KEY }),
  });
}

export function useUploadCertificateFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, kind, file }: { id: string; kind: "certificate" | "badge"; file: File }) =>
      apiClient.uploadFile<Certificate>(
        `/api/v1/career-profile/certifications/${id}/files/${kind}`,
        file,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CERTIFICATE_QUERY_KEY }),
  });
}

export function useDeleteCertificateFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, kind }: { id: string; kind: "certificate" | "badge" }) =>
      apiClient.delete(`/api/v1/career-profile/certifications/${id}/files/${kind}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CERTIFICATE_QUERY_KEY }),
  });
}

export function useCertificateFileUrl() {
  return useMutation({
    mutationFn: ({ id, kind }: { id: string; kind: "certificate" | "badge" }) =>
      apiClient.get<{ url: string }>(
        `/api/v1/career-profile/certifications/${id}/files/${kind}`,
      ),
  });
}

export function useShareCertificate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.post<{ share_key: string }>(
        `/api/v1/career-profile/certifications/${id}/share`,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CERTIFICATE_QUERY_KEY }),
  });
}

export function useRevokeCertificateShare() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.delete(`/api/v1/career-profile/certifications/${id}/share`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CERTIFICATE_QUERY_KEY }),
  });
}

export function usePublicCertificate(shareKey: string | undefined) {
  return useQuery({
    queryKey: ["public-certificate", shareKey],
    queryFn: () =>
      apiClient.get<PublicCertificate>(`/api/v1/public/certificates/${shareKey}`),
    enabled: !!shareKey,
    retry: false,
  });
}
