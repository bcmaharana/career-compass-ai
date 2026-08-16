import { ApiError } from "@/api/client";
import { useVerifySignup } from "@/api/queries/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineLink } from "@/components/ui/inline-link";
import { Compass } from "lucide-react";
import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

/**
 * Lands here from the link in a signup-verification email. No form —
 * the token alone is enough, so this auto-submits on mount and either
 * redirects straight into the app (verifying also logs the person in,
 * see useVerifySignup's onSuccess) or shows a clear error.
 *
 * The token is consumed server-side on first use — a ref guards against
 * firing the mutation twice from React StrictMode's dev-mode double
 * effect invocation, which would otherwise make the second call fail
 * with a confusing "invalid or expired" error for a token that actually
 * just got consumed by the first (successful) call a moment earlier.
 *
 * The mutate() call itself is deferred a tick via setTimeout rather than
 * called synchronously in the effect body — verified live that without
 * this, StrictMode's dev-mode double effect invocation (mount -> cleanup
 * -> remount, all synchronous within the same commit) tears down and
 * rebuilds useMutation's internal subscription *while* the very first
 * mutate() call's async response is still in flight. That first call's
 * promise still resolves/rejects for real, but its onSuccess/onError/
 * onSettled callbacks never fire and the component never re-renders —
 * the request genuinely completes (confirmed via network log) while the
 * UI stays frozen on "Verifying..." forever. Deferring past the
 * synchronous double-invoke window means mutate() only ever fires once
 * the post-StrictMode-cycling, stable subscription is in place; the
 * setTimeout's cleanup cancels the first (StrictMode-only) pass before
 * its callback body — including the `hasSubmitted` guard itself — ever
 * runs, so the second, stable pass is the one that actually submits.
 */
export function VerifyEmailPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const verifySignup = useVerifySignup();
  const hasSubmitted = useRef(false);

  useEffect(() => {
    if (!token) return;
    const timer = setTimeout(() => {
      if (hasSubmitted.current) return;
      hasSubmitted.current = true;
      verifySignup.mutate(
        { token },
        { onSuccess: () => navigate("/dashboard", { replace: true }) },
      );
    }, 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const errorMessage =
    verifySignup.error instanceof ApiError
      ? verifySignup.error.message
      : verifySignup.isError
        ? "Something went wrong verifying your email. Please try again."
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
              Verifying your email
            </CardTitle>
            <CardDescription>Just a moment while we confirm your account.</CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            {!token ? (
              <div className="flex flex-col gap-4">
                <p className="text-sm text-destructive">
                  This verification link is missing its token. Please sign up again.
                </p>
                <InlineLink to="/signup" className="text-sm">
                  Back to sign up
                </InlineLink>
              </div>
            ) : errorMessage ? (
              <div className="flex flex-col gap-4">
                <p role="alert" className="text-sm text-destructive">
                  {errorMessage}
                </p>
                <InlineLink to="/signup" className="text-sm">
                  Back to sign up
                </InlineLink>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Verifying...</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
