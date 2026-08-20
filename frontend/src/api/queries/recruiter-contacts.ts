import { apiClient } from "@/api/client";
import type { components } from "@/api/schema.gen";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type RecruiterContactRequest = components["schemas"]["RecruiterContactRequest"];
type RecruiterContactResponse = components["schemas"]["RecruiterContactResponse"];
type AddContactNoteRequest = components["schemas"]["AddContactNoteRequest"];

const KEYS = {
  contacts: ["recruiter-contacts"] as const,
};

export function useRecruiterContacts() {
  return useQuery({
    queryKey: KEYS.contacts,
    queryFn: () => apiClient.get<RecruiterContactResponse[]>("/api/v1/recruiter-contacts"),
  });
}

export function useCreateRecruiterContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: RecruiterContactRequest) =>
      apiClient.post<RecruiterContactResponse>("/api/v1/recruiter-contacts", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.contacts }),
  });
}

export function useUpdateRecruiterContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: RecruiterContactRequest }) =>
      apiClient.patch<RecruiterContactResponse>(`/api/v1/recruiter-contacts/${id}`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.contacts }),
  });
}

export function useAddRecruiterContactNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: AddContactNoteRequest }) =>
      apiClient.post<RecruiterContactResponse>(`/api/v1/recruiter-contacts/${id}/notes`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.contacts }),
  });
}

export function useDeleteRecruiterContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<void>(`/api/v1/recruiter-contacts/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEYS.contacts }),
  });
}
