import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Compass } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

/**
 * Honest "coming soon" placeholder, not a broken form. The backend
 * wrapper endpoint for self-serve signup (thin layer over the existing
 * RegisterTenantService, POST /api/v1/identity/tenants) doesn't exist
 * yet — this page exists so the landing page's CTAs aren't dead links
 * while that ships.
 */
export function SignupPage() {
  const [searchParams] = useSearchParams();
  const type = searchParams.get("type") === "organization" ? "organization" : "individual";

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
            <CardTitle>Self-serve sign-up is on the way</CardTitle>
            <CardDescription>
              {type === "organization"
                ? "Team/organization sign-up is coming soon."
                : "Individual sign-up is coming soon."}
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center text-sm text-muted-foreground">
            <p>
              We're finishing this flow. In the meantime, if your organization already has a
              Career Compass workspace, you can{" "}
              <Link to="/login" className="font-medium text-foreground underline">
                log in here
              </Link>
              .
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
