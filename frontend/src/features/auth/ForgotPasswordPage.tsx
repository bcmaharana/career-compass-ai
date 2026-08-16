import { useRequestPasswordReset } from "@/api/queries/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineLink } from "@/components/ui/inline-link";
import { Label } from "@/components/ui/label";
import { RainbowBorderInput } from "@/components/ui/rainbow-border-input";
import { cn } from "@/lib/utils";
import { Compass } from "lucide-react";
import { type FormEvent, useState } from "react";

/**
 * "Forgot password" request screen. Always shows the same generic
 * "check your email" message after a successful submit, regardless of
 * whether the subdomain/email combination was real — the backend
 * (RequestPasswordResetService) is deliberately uninformative on
 * purpose, so this page must never try to infer account existence from
 * the response, only from mutation.isSuccess itself.
 *
 * Personal/Enterprise toggle mirrors LoginPage's — Personal accounts
 * never have a subdomain to enter, at signup, login, or here.
 */
export function ForgotPasswordPage() {
  const requestReset = useRequestPasswordReset();

  const [accountType, setAccountType] = useState<"personal" | "enterprise">("personal");
  const [subdomain, setSubdomain] = useState("");
  const [email, setEmail] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    requestReset.mutate(accountType === "personal" ? { email } : { subdomain, email });
  }

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
              Reset your password
            </CardTitle>
            <CardDescription>
              {accountType === "personal"
                ? "Enter your email — if an account exists, we'll send a reset link."
                : "Enter your organization and email — if an account exists, we'll send a reset link."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {requestReset.isSuccess ? (
              <div className="flex flex-col gap-4 text-center">
                <p className="text-sm text-foreground">
                  If an account exists for that email, a reset link has been sent. Check your
                  inbox — the link expires in 30 minutes.
                </p>
                <InlineLink to="/login" className="text-sm">
                  Back to sign in
                </InlineLink>
              </div>
            ) : (
              <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
                <div className="grid grid-cols-2 gap-1 rounded-md bg-muted p-1">
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

                <Button
                  type="submit"
                  className="mt-2 w-full"
                  disabled={requestReset.isPending}
                >
                  {requestReset.isPending ? "Sending..." : "Send reset link"}
                </Button>

                <InlineLink to="/login" className="text-center text-sm">
                  Back to sign in
                </InlineLink>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
