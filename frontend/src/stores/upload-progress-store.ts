import { create } from "zustand";

/**
 * Tracks whether a resume upload/extraction request is currently
 * in-flight, from this browser tab's perspective — a standalone Zustand
 * store rather than component state because it must survive UploadCard
 * itself unmounting/remounting (leaving Resume Intelligence and coming
 * back, or just switching to the review screen) — a fresh `useState`
 * would forget an in-flight upload the moment its component unmounts,
 * losing the "may still be processing" notice this drives (see
 * ResumeIntelligencePage.tsx's UploadCard) the next time the user
 * returns to the page.
 *
 * `uploadToken` lives here too, not just in a component-local ref, for
 * the same reason: a real bug caught live — a fresh mount (leaving and
 * returning to the page while an earlier upload was still marked
 * in-flight) showed the "may still be processing" notice but had no way
 * to actually cancel from it, since a local ref set by the ORIGINAL
 * mount's handleChange doesn't exist in this new one. Persisting the
 * token here means any mount can call the backend's
 * /upload/{upload_token}/cancel with the right token, regardless of
 * which mount originally started the upload.
 */
interface UploadProgressState {
  isUploading: boolean;
  uploadToken: string | null;
  startUpload: (uploadToken: string) => void;
  clearUpload: () => void;
}

export const useUploadProgressStore = create<UploadProgressState>((set) => ({
  isUploading: false,
  uploadToken: null,
  startUpload: (uploadToken) => set({ isUploading: true, uploadToken }),
  clearUpload: () => set({ isUploading: false, uploadToken: null }),
}));
