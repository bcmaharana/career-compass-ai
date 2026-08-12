import { ApiError } from "@/api/client";
import { useRequestOrganizationSignup, useRequestPersonalSignup } from "@/api/queries/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RainbowBorderInput } from "@/components/ui/rainbow-border-input";
import { RainbowBorderPasswordInput } from "@/components/ui/rainbow-border-password-input";
import { ArrowLeft, Compass } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

/**
 * Real self-serve signup, replacing the earlier "coming soon"
 * placeholder. Two independent forms gated on the existing `?type=`
 * param from LandingPage's CTAs:
 *
 * - Personal: name + email + password only — no organization/subdomain
 *   field at all, ever. POSTs to /signup/personal, which derives a
 *   subdomain server-side (see backend's derive_personal_subdomain).
 * - Enterprise: the existing tenant-registration fields
 *   (RegisterTenantService's shape), unchanged.
 *
 * Neither path creates an account directly anymore — both are request
 * steps for email verification (see VerifyEmailPage.tsx). Submitting
 * either form shows a "check your email" confirmation, the same
 * pattern ForgotPasswordPage.tsx already established, rather than
 * navigating straight into the app.
 */
export function SignupPage() {
  const [searchParams] = useSearchParams();
  const type = searchParams.get("type") === "organization" ? "organization" : "individual";

  const personalSignup = useRequestPersonalSignup();
  const organizationSignup = useRequestOrganizationSignup();

  const [mismatchError, setMismatchError] = useState(false);

  // Personal form state
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [personalEmail, setPersonalEmail] = useState("");
  const [personalPassword, setPersonalPassword] = useState("");
  const [personalConfirmPassword, setPersonalConfirmPassword] = useState("");
  const [personalAgreedToTerms, setPersonalAgreedToTerms] = useState(false);

  // Enterprise form state
  const [tenantName, setTenantName] = useState("");
  const [subdomain, setSubdomain] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [adminFirstName, setAdminFirstName] = useState("");
  const [adminLastName, setAdminLastName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminConfirmPassword, setAdminConfirmPassword] = useState("");
  const [enterpriseAgreedToTerms, setEnterpriseAgreedToTerms] = useState(false);

  function handlePersonalSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (personalPassword !== personalConfirmPassword) {
      setMismatchError(true);
      return;
    }
    setMismatchError(false);
    personalSignup.mutate({
      email: personalEmail,
      password: personalPassword,
      first_name: firstName,
      last_name: lastName,
      agreed_to_terms: personalAgreedToTerms,
    });
  }

  function handleEnterpriseSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (adminPassword !== adminConfirmPassword) {
      setMismatchError(true);
      return;
    }
    setMismatchError(false);
    organizationSignup.mutate({
      tenant_name: tenantName,
      subdomain,
      organization_name: organizationName,
      admin_email: adminEmail,
      admin_first_name: adminFirstName,
      admin_last_name: adminLastName,
      admin_password: adminPassword,
      agreed_to_terms: enterpriseAgreedToTerms,
    });
  }

  const activeMutation = type === "individual" ? personalSignup : organizationSignup;
  const errorMessage = mismatchError
    ? "Passwords don't match."
    : activeMutation.error instanceof ApiError
      ? activeMutation.error.message
      : activeMutation.isError
        ? "Something went wrong. Please try again."
        : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
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

      <div className="w-full max-w-md">
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
                {type === "organization" ? "Set up your team" : "Create your account"}
              </CardTitle>
              <CardDescription>
                {type === "organization"
                  ? "For your organization — you'll manage access for your team."
                  : "For yourself — just a name, email, and password."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {activeMutation.isSuccess ? (
                <div className="flex flex-col gap-4 text-center">
                  <p className="text-sm text-foreground">
                    Check your email for a verification link to finish creating your account. The
                    link expires in 60 minutes.
                  </p>
                  <Link to="/login" className="text-sm text-muted-foreground hover:text-foreground">
                    Back to sign in
                  </Link>
                </div>
              ) : type === "individual" ? (
                <form className="flex flex-col gap-4" onSubmit={handlePersonalSubmit}>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="first-name">First name</Label>
                      <RainbowBorderInput
                        id="first-name"
                        autoComplete="given-name"
                        required
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="last-name">Last name</Label>
                      <RainbowBorderInput
                        id="last-name"
                        autoComplete="family-name"
                        required
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="personal-email">Email</Label>
                    <RainbowBorderInput
                      id="personal-email"
                      type="email"
                      autoComplete="email"
                      required
                      value={personalEmail}
                      onChange={(e) => setPersonalEmail(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="personal-password">Password</Label>
                    <RainbowBorderPasswordInput
                      id="personal-password"
                      autoComplete="new-password"
                      minLength={8}
                      required
                      value={personalPassword}
                      onChange={(e) => setPersonalPassword(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="personal-confirm-password">Confirm password</Label>
                    <RainbowBorderPasswordInput
                      id="personal-confirm-password"
                      autoComplete="new-password"
                      minLength={8}
                      required
                      value={personalConfirmPassword}
                      onChange={(e) => setPersonalConfirmPassword(e.target.value)}
                    />
                  </div>

                  <label className="flex items-start gap-2 text-sm text-muted-foreground">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 rounded border-border"
                      checked={personalAgreedToTerms}
                      onChange={(e) => setPersonalAgreedToTerms(e.target.checked)}
                    />
                    <span>
                      I agree to the{" "}
                      <Link to="/terms" target="_blank" className="text-foreground underline">
                        Terms of Service
                      </Link>{" "}
                      and{" "}
                      <Link to="/privacy" target="_blank" className="text-foreground underline">
                        Privacy Policy
                      </Link>
                      .
                    </span>
                  </label>

                  {errorMessage && (
                    <p role="alert" className="text-sm text-destructive">
                      {errorMessage}
                    </p>
                  )}

                  <Button
                    type="submit"
                    className="mt-2 w-full"
                    disabled={personalSignup.isPending || !personalAgreedToTerms}
                  >
                    {personalSignup.isPending ? "Sending verification email..." : "Create account"}
                  </Button>
                </form>
              ) : (
                <form className="flex flex-col gap-4" onSubmit={handleEnterpriseSubmit}>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="tenant-name">Company name</Label>
                    <RainbowBorderInput
                      id="tenant-name"
                      required
                      value={tenantName}
                      onChange={(e) => setTenantName(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="org-subdomain">Organization ID</Label>
                    <RainbowBorderInput
                      id="org-subdomain"
                      placeholder="acme"
                      pattern="[a-z0-9\-]+"
                      title="Lowercase letters, numbers, and hyphens only"
                      required
                      value={subdomain}
                      onChange={(e) => setSubdomain(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">
                      This is what your team will use to sign in — lowercase letters, numbers, and
                      hyphens only.
                    </p>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="organization-name">Department/team name</Label>
                    <RainbowBorderInput
                      id="organization-name"
                      required
                      value={organizationName}
                      onChange={(e) => setOrganizationName(e.target.value)}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="admin-first-name">Your first name</Label>
                      <RainbowBorderInput
                        id="admin-first-name"
                        autoComplete="given-name"
                        required
                        value={adminFirstName}
                        onChange={(e) => setAdminFirstName(e.target.value)}
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="admin-last-name">Your last name</Label>
                      <RainbowBorderInput
                        id="admin-last-name"
                        autoComplete="family-name"
                        required
                        value={adminLastName}
                        onChange={(e) => setAdminLastName(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="admin-email">Work email</Label>
                    <RainbowBorderInput
                      id="admin-email"
                      type="email"
                      autoComplete="email"
                      required
                      value={adminEmail}
                      onChange={(e) => setAdminEmail(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="admin-password">Password</Label>
                    <RainbowBorderPasswordInput
                      id="admin-password"
                      autoComplete="new-password"
                      minLength={8}
                      required
                      value={adminPassword}
                      onChange={(e) => setAdminPassword(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="admin-confirm-password">Confirm password</Label>
                    <RainbowBorderPasswordInput
                      id="admin-confirm-password"
                      autoComplete="new-password"
                      minLength={8}
                      required
                      value={adminConfirmPassword}
                      onChange={(e) => setAdminConfirmPassword(e.target.value)}
                    />
                  </div>

                  <label className="flex items-start gap-2 text-sm text-muted-foreground">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 rounded border-border"
                      checked={enterpriseAgreedToTerms}
                      onChange={(e) => setEnterpriseAgreedToTerms(e.target.checked)}
                    />
                    <span>
                      I agree to the{" "}
                      <Link to="/terms" target="_blank" className="text-foreground underline">
                        Terms of Service
                      </Link>{" "}
                      and{" "}
                      <Link to="/privacy" target="_blank" className="text-foreground underline">
                        Privacy Policy
                      </Link>
                      .
                    </span>
                  </label>

                  {errorMessage && (
                    <p role="alert" className="text-sm text-destructive">
                      {errorMessage}
                    </p>
                  )}

                  <Button
                    type="submit"
                    className="mt-2 w-full"
                    disabled={organizationSignup.isPending || !enterpriseAgreedToTerms}
                  >
                    {organizationSignup.isPending
                      ? "Sending verification email..."
                      : "Set up your team"}
                  </Button>
                </form>
              )}

              {!activeMutation.isSuccess && (
                <p className="mt-4 text-center text-sm text-muted-foreground">
                  Already have an account?{" "}
                  <Link to="/login" className="font-medium text-foreground underline">
                    Log in
                  </Link>
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
