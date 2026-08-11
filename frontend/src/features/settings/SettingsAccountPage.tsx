import { useDeleteAccount } from "@/api/queries/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/errors";
import { useAuthStore } from "@/stores/auth-store";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

const CONFIRM_PHRASE = "DELETE";

/**
 * Real, permanent account deletion — no grace period, no undo (see
 * DeleteAccountService's docstring on the backend). This is the one
 * place in the app that needs more than the standard single-click
 * ConfirmDialog (components/ui/confirm-dialog.tsx) — a plain "are you
 * sure?" is proportionate for deleting a career-profile entry, not for
 * an irreversible action that removes every entry, resume, and the
 * account itself. Typing the confirmation phrase is its own dedicated
 * dialog here rather than a new variant bolted onto the shared
 * ConfirmDialog, since this is currently the only place that needs it.
 */
export function SettingsAccountPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const clearSession = useAuthStore((state) => state.clearSession);
  const deleteAccount = useDeleteAccount();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [confirmText, setConfirmText] = useState("");

  function handleConfirmDelete() {
    deleteAccount.mutate(undefined, {
      onSuccess: () => {
        clearSession();
        // Same reasoning as AppShell's own sign-out handler — the query
        // cache is a module-level singleton, not scoped per session.
        queryClient.clear();
        navigate("/", { replace: true });
      },
    });
  }

  function closeDialog() {
    if (deleteAccount.isPending) return;
    setDialogOpen(false);
    setConfirmText("");
  }

  return (
    <Card className="max-w-xl border-destructive/50">
      <CardHeader>
        <CardTitle className="text-destructive">Delete account</CardTitle>
        <CardDescription>
          Permanently deletes your account and everything in it — your career profile, resumes,
          chat history, and login. This cannot be undone.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button variant="destructive" onClick={() => setDialogOpen(true)}>
          Delete my account
        </Button>

        {deleteAccount.isError && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {getErrorMessage(deleteAccount.error)}
          </p>
        )}
      </CardContent>

      <Dialog open={dialogOpen} onClose={closeDialog} title="Delete your account?">
        <p className="text-sm text-muted-foreground">
          This permanently deletes your account and all of your data. There is no way to undo
          this or recover it afterward.
        </p>
        <div className="mt-4 flex flex-col gap-1.5">
          <Label htmlFor="delete-confirm-text">
            Type <span className="font-mono font-semibold">{CONFIRM_PHRASE}</span> to confirm
          </Label>
          <Input
            id="delete-confirm-text"
            autoComplete="off"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            disabled={deleteAccount.isPending}
          />
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={closeDialog} disabled={deleteAccount.isPending}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirmDelete}
            disabled={confirmText !== CONFIRM_PHRASE || deleteAccount.isPending}
          >
            {deleteAccount.isPending ? "Deleting..." : "Permanently delete"}
          </Button>
        </div>
      </Dialog>
    </Card>
  );
}
