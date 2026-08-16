import { ApiError } from "@/api/client";
import { useResetPassword } from "@/api/queries/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineLink } from "@/components/ui/inline-link";
import { Label } from "@/components/ui/label";
import { RainbowBorderInput } from "@/components/ui/rainbow-border-input";
import { Compass } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

/**
 * "Set new password" screen, reached from the link in the password-reset
 * email. The token lives in the URL query string, never typed by the
 * user — a missing token means this page was reached some other way
 * (bookmarked, link mangled by an email client, etc.), so that's caught
 * before ever round-tripping to the backend.
 */
export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const resetPassword = useResetPassword();

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mismatchError, setMismatchError] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      setMismatchError(true);
      return;
    }
    setMismatchError(false);
    resetPassword.mutate(
      { token, new_password: newPassword },
      { onSuccess: () => navigate("/login", { replace: true }) },
    );
  }

  const errorMessage = mismatchError
    ? "Passwords don't match."
    : resetPassword.error instanceof ApiError
      ? resetPassword.error.message
      : resetPassword.isError
        ? "Something went wrong resetting your password. Please try again."
        : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <svg width="0" height="0" className="absolute" aria-hidden="true">
        <defs>
          <linearGradient id="rainbow-accent-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="12.5%" stopColor="#a855f7" />
            <stop offset="37.5%" stopColor="#3b82f6" />
            <stop offset="58.33%" stopColor="#22c55e" />
            <stop offset="75%" stopColor="#fdba74" />
            <stop offset="91.67%" stopColor="#fca5a5" />
          </linearGradient>
        </defs>
      </svg>

      <div className="w-full max-w-sm rounded-lg bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] p-1.5">
        <Card className="border-0">
          <CardHeader className="items-center text-center">
            <Compass
              className="mb-2 h-8 w-8"
              strokeWidth={2}
              color="url(#rainbow-accent-gradient)"
            />
            <CardTitle
              className="bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] bg-clip-text text-transparent"
            >
              Set a new password
            </CardTitle>
            <CardDescription>Choose a new password for your account.</CardDescription>
          </CardHeader>
          <CardContent>
            {!token ? (
              <div className="flex flex-col gap-4 text-center">
                <p className="text-sm text-destructive">
                  This reset link is missing its token. Please request a new one.
                </p>
                <InlineLink to="/forgot-password" className="text-sm">
                  Request a new reset link
                </InlineLink>
              </div>
            ) : (
              <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="new-password">New password</Label>
                  <RainbowBorderInput
                    id="new-password"
                    type="password"
                    autoComplete="new-password"
                    minLength={8}
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="confirm-password">Confirm new password</Label>
                  <RainbowBorderInput
                    id="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    minLength={8}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                </div>

                {errorMessage && (
                  <p role="alert" className="text-sm text-destructive">
                    {errorMessage}
                  </p>
                )}

                <Button
                  type="submit"
                  className="mt-2 w-full"
                  disabled={resetPassword.isPending}
                >
                  {resetPassword.isPending ? "Resetting..." : "Reset password"}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
