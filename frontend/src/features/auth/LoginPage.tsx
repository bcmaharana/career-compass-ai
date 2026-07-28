import { ApiError } from "@/api/client";
import { useLogin } from "@/api/queries/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { Compass } from "lucide-react";
import { type ComponentProps, type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

/**
 * A normal-width (1px) rainbow border — the gradient-padding trick from
 * the card border below, just with 1px of padding instead of 6px, so it
 * reads as "recolored border" rather than "thick frame." border-image
 * would be the more obvious CSS tool for a gradient border, but it
 * doesn't respect border-radius, so it'd square off Input's rounded
 * corners — this nested-box approach doesn't have that problem at any
 * thickness.
 */
function RainbowBorderInput({ className, ...props }: ComponentProps<typeof Input>) {
  return (
    <div className="rounded-md bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] p-px">
      <Input {...props} className={cn("border-0", className)} />
    </div>
  );
}

/**
 * Sign-in screen, wired to the real Phase 1 identity service
 * (POST /api/v1/identity/login). Subdomain is a separate field rather
 * than folded into email because tenants are resolved by subdomain, not
 * inferred from the email's domain — see
 * app/application/identity/authenticate_user.py on the backend for why.
 */
export function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();

  const [subdomain, setSubdomain] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    login.mutate(
      { subdomain, email, password },
      { onSuccess: () => navigate("/", { replace: true }) },
    );
  }

  const errorMessage =
    login.error instanceof ApiError
      ? login.error.message
      : login.isError
        ? "Something went wrong signing in. Please try again."
        : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      {/* Hidden defs only — provides #rainbow-accent-gradient for the
          compass icon's stroke below. LoginPage sits outside AppShell
          (no session yet), so it needs its own copy of this def rather
          than reusing AppShell's. */}
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
              Sign in to Career Compass
            </CardTitle>
            <CardDescription>Continuous career intelligence for you and your team.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="subdomain">Organization</Label>
                <RainbowBorderInput
                  id="subdomain"
                  type="text"
                  placeholder="acme"
                  autoComplete="organization"
                  required
                  value={subdomain}
                  onChange={(e) => setSubdomain(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="email">Work email</Label>
                <RainbowBorderInput
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="password">Password</Label>
                <RainbowBorderInput
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              {errorMessage && (
                <p role="alert" className="text-sm text-destructive">
                  {errorMessage}
                </p>
              )}

              <Button type="submit" className="mt-2 w-full" disabled={login.isPending}>
                {login.isPending ? "Signing in..." : "Sign in"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
