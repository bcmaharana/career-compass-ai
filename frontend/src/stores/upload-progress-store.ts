import { create } from "zustand";

/**
 * Tracks whether a resume upload/extraction request is currently
 * in-flight, from this browser tab's perspective — a standalone Zustand
 * store rather than component state because it needs to be visible
 * outside ResumeIntelligencePage.tsx: a real gap, not a hypothetical
 * one, was a user clicking any other Left/Right Nav link mid-upload
 * getting no warning at all that navigating away would abandon the
 * browser's wait on a request that — per this app's own documented
 * Docker-Desktop-networking gotcha — may well keep running server-side
 * regardless. See UploadNavigationGuard.tsx, the component that reads
 * this to actually block navigation.
 */
interface UploadProgressState {
  isUploading: boolean;
  setUploading: (isUploading: boolean) => void;
}

export const useUploadProgressStore = create<UploadProgressState>((set) => ({
  isUploading: false,
  setUploading: (isUploading) => set({ isUploading }),
}));
