import { ApiError } from "@/api/client";
import { usePlatformHandoff } from "@/api/queries/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineLink } from "@/components/ui/inline-link";
import { Compass } from "lucide-react";
import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

/**
 * Lands here when Platform Identity (the sibling `enterprise/platform`
 * marketing/SSO site) sends a signed-in visitor to Career Compass AI —
 * `?token=` carries a Platform Identity JWT, exchanged here for a normal
 * CCAI session via POST /identity/platform-handoff. See
 * docs/adr/ADR-010-platform-identity-integration.md.
 *
 * Deliberately the same auto-submit-on-mount shape as VerifyEmailPage.tsx
 * (no form — the token alone is enough) including its StrictMode fix:
 * the mutate() call is deferred a tick via setTimeout and guarded by a
 * ref, since a synchronous mutate() in the effect body was verified live
 * to leave the UI frozen on "Signing you in..." forever under React 18
 * StrictMode's dev-only double effect invocation — see that file's own
 * docstring for the full root-cause writeup, which applies unchanged
 * here.
 */
export function PlatformHandoffPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  // Which of possibly several active entitlements to honor (Personal vs
  // a specific Enterprise org) — set by the platform's own scope picker
  // when there's a real choice to make; omitted (undefined) for the
  // common single-scope case, matching PlatformHandoffRequest.org_id's
  // own "None = take whichever's first" default on the backend.
  const orgId = searchParams.get("org_id") ?? undefined;
  const platformHandoff = usePlatformHandoff();
  const hasSubmitted = useRef(false);

  useEffect(() => {
    if (!token) return;
    const timer = setTimeout(() => {
      if (hasSubmitted.current) return;
      hasSubmitted.current = true;
      platformHandoff.mutate(
        { platform_token: token, org_id: orgId },
        { onSuccess: () => navigate("/welcome", { replace: true }) },
      );
    }, 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const errorMessage =
    platformHandoff.error instanceof ApiError
      ? platformHandoff.error.message
      : platformHandoff.isError
        ? "Something went wrong signing you in. Please try again."
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
              Signing you in
            </CardTitle>
            <CardDescription>Just a moment while we connect your account.</CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            {!token ? (
              <div className="flex flex-col gap-4">
                <p className="text-sm text-destructive">
                  This sign-in link is missing its token.
                </p>
                <InlineLink to="/login" className="text-sm">
                  Go to login
                </InlineLink>
              </div>
            ) : errorMessage ? (
              <div className="flex flex-col gap-4">
                <p role="alert" className="text-sm text-destructive">
                  {errorMessage}
                </p>
                <InlineLink to="/login" className="text-sm">
                  Go to login
                </InlineLink>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Signing you in...</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
