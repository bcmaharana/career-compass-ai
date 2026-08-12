import { ApiError } from "@/api/client";
import { useLogin } from "@/api/queries/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RainbowBorderInput } from "@/components/ui/rainbow-border-input";
import { RainbowBorderPasswordInput } from "@/components/ui/rainbow-border-password-input";
import { PhoneLoginForm } from "@/features/auth/PhoneLoginForm";
import { cn } from "@/lib/utils";
import { ArrowLeft, Compass } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

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

  // Personal accounts never have (or need to know) a subdomain — for
  // email login the backend derives one deterministically from the
  // email (see derive_personal_subdomain on the backend); for phone
  // login it resolves the tenant via personal_phone_logins instead
  // (see AuthenticateUserService.execute_phone) — either way, the
  // Organization field itself is Enterprise-only, not the Phone tab
  // (PhoneLoginForm's showOrganizationField prop below).
  const [accountType, setAccountType] = useState<"personal" | "enterprise">("personal");
  const [method, setMethod] = useState<"email" | "phone">("email");
  // Shared across both tabs (rather than each owning its own copy) so
  // switching tabs mid-entry doesn't make the user retype which
  // organization they're signing into.
  const [subdomain, setSubdomain] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    login.mutate(
      accountType === "personal" ? { email, password } : { subdomain, email, password },
      { onSuccess: () => navigate("/dashboard", { replace: true }) },
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

      <div className="w-full max-w-sm">
        <Link
          to="/"
          className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to home
        </Link>
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
                Sign in to Career Compass
              </CardTitle>
              <CardDescription>Continuous career intelligence for you and your team.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4 grid grid-cols-2 gap-1 rounded-md bg-muted p-1">
                {(["personal", "enterprise"] as const).map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setAccountType(option)}
                    className={cn(
                      "rounded-sm py-1.5 text-sm font-medium transition-colors",
                      accountType === option
                        ? "bg-card text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {option === "personal" ? "Personal" : "Enterprise"}
                  </button>
                ))}
              </div>

              <div className="mb-4 grid grid-cols-2 gap-1 rounded-md bg-muted p-1">
                {(["email", "phone"] as const).map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setMethod(option)}
                    className={cn(
                      "rounded-sm py-1.5 text-sm font-medium transition-colors",
                      method === option
                        ? "bg-card text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {option === "email" ? "Email" : "Phone"}
                  </button>
                ))}
              </div>

              {method === "email" ? (
                <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
                  {accountType === "enterprise" && (
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
                  )}
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="email">{accountType === "personal" ? "Email" : "Work email"}</Label>
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
                    <div className="flex items-center justify-between">
                      <Label htmlFor="password">Password</Label>
                      <Link
                        to="/forgot-password"
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        Forgot password?
                      </Link>
                    </div>
                    <RainbowBorderPasswordInput
                      id="password"
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
              ) : (
                <PhoneLoginForm
                  subdomain={subdomain}
                  onSubdomainChange={setSubdomain}
                  showOrganizationField={accountType === "enterprise"}
                />
              )}

              <p className="mt-4 text-center text-sm text-muted-foreground">
                Don't have an account?{" "}
                <Link to="/signup" className="font-medium text-foreground underline">
                  Sign up
                </Link>
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
