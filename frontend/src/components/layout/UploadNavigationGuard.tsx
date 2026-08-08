import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useUploadProgressStore } from "@/stores/upload-progress-store";
import { useEffect } from "react";
import { useBlocker } from "react-router-dom";

/**
 * Warns before the user navigates away while a resume upload is
 * in-flight — a real gap found live: clicking any Left/Right Nav link
 * mid-upload navigated away with no warning at all, silently abandoning
 * the browser's wait on a request that, per this app's own documented
 * Docker-Desktop-networking gotcha (see ResumeIntelligencePage.tsx's
 * UploadCard), may well keep running server-side regardless — the user
 * has no way to know whether it finished, failed, or is still going.
 *
 * Rendered once, in AppShell.tsx (outside any single route), rather than
 * inside ResumeIntelligencePage.tsx itself — the whole point is to catch
 * navigation FROM that page to anywhere else, so it can't live inside
 * the page it's protecting against leaving.
 *
 * Two mechanisms, since they cover different kinds of "leaving":
 * useBlocker (react-router-dom, requires the data router this app
 * already uses via createBrowserRouter) intercepts in-app navigation —
 * clicking a NavLink, calling navigate() — and lets a custom ConfirmDialog
 * ask before it happens. `beforeunload` is the only way to warn on an
 * actual tab close/refresh/typed URL — browsers show their own
 * un-customizable native prompt for that, never this app's UI.
 */
export function UploadNavigationGuard() {
  const isUploading = useUploadProgressStore((state) => state.isUploading);

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      isUploading && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      if (!isUploading) return;
      event.preventDefault();
      // Legacy assignment some browsers still require to actually show
      // their native "leave site?" prompt — the string itself is never
      // displayed by any modern browser, which always uses their own
      // fixed wording instead.
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isUploading]);

  return (
    <ConfirmDialog
      open={blocker.state === "blocked"}
      onCancel={() => blocker.state === "blocked" && blocker.reset()}
      onConfirm={() => blocker.state === "blocked" && blocker.proceed()}
      title="Leave while your resume is uploading?"
      description="Your resume is still being uploaded and analyzed. Leaving this page won't necessarily stop it — the analysis may keep running in the background and appear in your Resume History later — but you'll lose sight of it finishing. Stay on this page, or leave anyway?"
      confirmLabel="Leave anyway"
      confirmPendingLabel="Leave anyway"
    />
  );
}
