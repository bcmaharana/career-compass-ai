import { ApiError } from "@/api/client";
import { usePhoneLogin } from "@/api/queries/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { FirebaseNotConfiguredError, getFirebaseAuth } from "@/lib/firebase";
import { getCountryOptions } from "@/lib/locale-options";
import { formatPhoneForCountry, toE164 } from "@/lib/phone-format";
import { cn } from "@/lib/utils";
import { FirebaseError } from "firebase/app";
import { RecaptchaVerifier, signInWithPhoneNumber, type ConfirmationResult } from "firebase/auth";
import { type ComponentProps, type FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

const COUNTRY_OPTIONS = getCountryOptions();

function RainbowBorderInput({ className, ...props }: ComponentProps<typeof Input>) {
  return (
    <div className="rounded-md bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] p-px">
      <Input {...props} className={cn("border-0", className)} />
    </div>
  );
}

/** Maps Firebase Auth's error codes to plain-language messages — the raw
 * codes ("auth/invalid-phone-number") are meaningless to an end user. */
function firebaseErrorMessage(error: unknown): string {
  if (error instanceof FirebaseNotConfiguredError) {
    return "Phone login isn't set up yet — please sign in with email for now.";
  }
  if (error instanceof FirebaseError) {
    switch (error.code) {
      case "auth/invalid-phone-number":
        return "That doesn't look like a valid phone number for the selected country.";
      case "auth/too-many-requests":
        return "Too many attempts. Please wait a while before trying again.";
      case "auth/invalid-verification-code":
        return "That code isn't right. Double-check it and try again.";
      case "auth/code-expired":
        return "That code has expired — request a new one.";
      case "auth/captcha-check-failed":
        return "Verification failed. Please refresh and try again.";
      default:
        return "Something went wrong sending the code. Please try again.";
    }
  }
  return "Something went wrong. Please try again.";
}

interface PhoneLoginFormProps {
  subdomain: string;
  onSubdomainChange: (value: string) => void;
}

/**
 * Phone login: an alternate LoginPage tab that authenticates via an SMS
 * one-time code instead of a password. Firebase Phone Auth (not this
 * app's own backend) owns sending the code and verifying it — this
 * component only ever talks to Firebase directly for that part (see
 * lib/firebase.ts) and, once Firebase confirms the code, hands the
 * resulting ID token to POST /api/v1/identity/login/phone (usePhoneLogin)
 * to get back the same session shape email/password login produces.
 *
 * Two steps: enter phone number (triggers Firebase's SMS send, backed by
 * an invisible reCAPTCHA Firebase requires to rate-limit abuse), then
 * enter the received code. "Change number" resets back to step one.
 *
 * The RecaptchaVerifier instance is created once (lazily, on first send
 * attempt) and deliberately reused for the component's whole lifetime,
 * torn down only on unmount — recreating it on every retry looked like
 * the safer choice but actually broke retries: the underlying grecaptcha
 * widget is tied to its container DOM node, and re-rendering a new
 * widget into that same node (even after calling .clear() on the old
 * verifier) throws "reCAPTCHA has already been rendered in this
 * element." A single invisible verifier is designed to be reused across
 * multiple signInWithPhoneNumber calls, so there's no need to recreate
 * it after a failed attempt anyway.
 */
export function PhoneLoginForm({ subdomain, onSubdomainChange }: PhoneLoginFormProps) {
  const navigate = useNavigate();
  const phoneLogin = usePhoneLogin();

  const [step, setStep] = useState<"phone" | "code">("phone");
  const [country, setCountry] = useState("US");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [code, setCode] = useState("");
  const [confirmationResult, setConfirmationResult] = useState<ConfirmationResult | null>(null);
  const [isSendingCode, setIsSendingCode] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recaptchaContainerRef = useRef<HTMLDivElement>(null);
  const recaptchaVerifierRef = useRef<RecaptchaVerifier | null>(null);

  useEffect(() => {
    return () => {
      recaptchaVerifierRef.current?.clear();
    };
  }, []);

  // Lazily creates the verifier on first use rather than in a mount
  // effect — the container div is always in the DOM by the time a form
  // submit can fire, so there's no ordering issue, and this avoids
  // creating a reCAPTCHA widget before the user has done anything. Once
  // created it's reused for every subsequent attempt (see the docstring
  // above) — never recreated just because a previous send failed.
  function getRecaptchaVerifier(): RecaptchaVerifier {
    if (!recaptchaVerifierRef.current && recaptchaContainerRef.current) {
      recaptchaVerifierRef.current = new RecaptchaVerifier(
        getFirebaseAuth(),
        recaptchaContainerRef.current,
        { size: "invisible" },
      );
    }
    return recaptchaVerifierRef.current as RecaptchaVerifier;
  }

  async function handleSendCode(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (!subdomain.trim()) {
      setError("Enter your organization first.");
      return;
    }
    const e164 = toE164(phoneNumber, country);
    if (!e164) {
      setError("Enter a valid phone number for the selected country.");
      return;
    }

    setIsSendingCode(true);
    try {
      const result = await signInWithPhoneNumber(getFirebaseAuth(), e164, getRecaptchaVerifier());
      setConfirmationResult(result);
      setStep("code");
    } catch (err) {
      // Logged so a rejected/unrecognized Firebase error code is visible
      // in DevTools rather than only ever showing the generic fallback
      // message — Firebase phone auth has several distinct real-world
      // failure modes (billing plan, unenabled provider, App Check) that
      // are much faster to diagnose from the raw error than by guessing.
      console.error("Phone login send-code failed:", err);
      setError(firebaseErrorMessage(err));
    } finally {
      setIsSendingCode(false);
    }
  }

  async function handleVerifyCode(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!confirmationResult) return;

    try {
      const credential = await confirmationResult.confirm(code);
      const idToken = await credential.user.getIdToken();
      phoneLogin.mutate(
        { subdomain, firebase_id_token: idToken },
        { onSuccess: () => navigate("/", { replace: true }) },
      );
    } catch (err) {
      setError(firebaseErrorMessage(err));
    }
  }

  function handleChangeNumber() {
    setConfirmationResult(null);
    setCode("");
    setError(null);
    setStep("phone");
  }

  const backendErrorMessage =
    phoneLogin.error instanceof ApiError
      ? phoneLogin.error.message
      : phoneLogin.isError
        ? "Something went wrong signing in. Please try again."
        : null;

  const errorMessage = error ?? backendErrorMessage;

  return (
    <>
      {/* Firebase renders its invisible reCAPTCHA widget into this node
          on demand — never visible itself, but must exist in the DOM
          before signInWithPhoneNumber is called. */}
      <div ref={recaptchaContainerRef} />

      {step === "phone" && (
        <form className="flex flex-col gap-4" onSubmit={handleSendCode}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="phone-subdomain">Organization</Label>
            <RainbowBorderInput
              id="phone-subdomain"
              type="text"
              placeholder="acme"
              autoComplete="organization"
              required
              value={subdomain}
              onChange={(e) => onSubdomainChange(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="phone-country">Country</Label>
            <Select
              id="phone-country"
              value={country}
              onChange={(e) => {
                setCountry(e.target.value);
                setPhoneNumber((current) => formatPhoneForCountry(current, e.target.value));
              }}
            >
              {COUNTRY_OPTIONS.map((option) => (
                <option key={option.code} value={option.code}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="phone-number">Phone number</Label>
            <RainbowBorderInput
              id="phone-number"
              type="tel"
              autoComplete="tel"
              required
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(formatPhoneForCountry(e.target.value, country))}
            />
          </div>

          {errorMessage && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage}
            </p>
          )}

          <Button type="submit" className="mt-2 w-full" disabled={isSendingCode}>
            {isSendingCode ? "Sending code..." : "Send code"}
          </Button>
        </form>
      )}

      {step === "code" && (
        <form className="flex flex-col gap-4" onSubmit={handleVerifyCode}>
          <p className="text-sm text-muted-foreground">
            We sent a code to {phoneNumber}.{" "}
            <button
              type="button"
              onClick={handleChangeNumber}
              className="font-medium text-accent underline-offset-2 hover:underline"
            >
              Change number
            </button>
          </p>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="phone-code">Verification code</Label>
            <RainbowBorderInput
              id="phone-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              required
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value.trim())}
            />
          </div>

          {errorMessage && (
            <p role="alert" className="text-sm text-destructive">
              {errorMessage}
            </p>
          )}

          <Button type="submit" className="mt-2 w-full" disabled={!code || phoneLogin.isPending}>
            {phoneLogin.isPending ? "Verifying..." : "Verify & sign in"}
          </Button>
        </form>
      )}
    </>
  );
}
