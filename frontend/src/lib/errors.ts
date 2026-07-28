import { ApiError } from "@/api/client";

/**
 * Extracts a user-facing message from whatever TanStack Query's
 * `mutation.error` holds. Centralized here so every form surfaces
 * failures the same way, rather than each component re-deriving it (and
 * some inevitably forgetting to) — a save that fails silently is
 * indistinguishable from a save that never happened, from the user's
 * point of view.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}
