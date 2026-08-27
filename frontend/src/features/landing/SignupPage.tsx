import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PLATFORM_BASE_URL } from "@/lib/platform";
import { Compass } from "lucide-react";
import { useEffect } from "react";

/**
 * Same reasoning as LoginPage.tsx — signup, like login, now only ever
 * happens on the platform. This page's own real Personal/Enterprise
 * signup UI (email-verification flow, Terms of Service checkbox) is
 * NOT deleted, just unreferenced — kept in case this needs to stand
 * alone again. The platform's own /signup already has an equivalent
 * Personal/Enterprise split and its own Terms/Privacy-equivalent
 * consideration is that repo's own concern now.
 */
export function SignupPage() {
  useEffect(() => {
    const redirectUri = `${window.location.origin}/platform-handoff`;
    window.location.replace(
      `${PLATFORM_BASE_URL}/signup?redirect_uri=${encodeURIComponent(redirectUri)}`,
    );
  }, []);

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

      <div className="w-full max-w-sm">
        <Breadcrumb segments={[{ label: "Career Compass AI" }]} className="mb-2 justify-center" />
        <div className="rounded-lg bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] p-1.5">
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
              Redirecting to sign up
            </CardTitle>
            <CardDescription>Taking you to the platform's sign-up page...</CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <p className="text-sm text-muted-foreground">
              Not redirected automatically?{" "}
              <a
                href={`${PLATFORM_BASE_URL}/signup`}
                className="font-medium text-accent underline underline-offset-2 hover:text-accent/80"
              >
                Sign up here
              </a>
            </p>
          </CardContent>
        </Card>
        </div>
      </div>
    </div>
  );
}
