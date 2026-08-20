import { useTargetRoles } from "@/api/queries/career-profile";
import { useQuoteOfTheDay } from "@/api/queries/quotes";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";
import { useTargetRoleScopeStore } from "@/stores/target-role-scope-store";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

const NO_ROLES_REDIRECT_DELAY_MS = 3000;

/**
 * Post-login landing page (`/welcome`) — both LoginPage.tsx and
 * VerifyEmailPage.tsx navigate here instead of straight to `/dashboard`
 * now, on every successful sign-in. Centered in AppShell's normal
 * scrollable panel (chrome stays visible, unlike LoginPage which sits
 * outside AppShell entirely) rather than a standalone full-screen
 * layout, so it doesn't need to duplicate the rainbow-gradient SVG defs
 * / header-less styling LoginPage has to carry for having no session yet.
 *
 * Doubles as the one deliberate entry point for setting the app-wide
 * "active target role" scope (target-role-scope-store.ts) at the start
 * of a session — picking a role here is exactly equivalent to picking
 * one from Career Profile's Target Roles widget or any other role-aware
 * page's own selector, it just asks up front instead of waiting for the
 * person to stumble onto one of those.
 *
 * Two branches, decided once `targetRoles` has loaded:
 *  - No target roles at all: nothing to ask, so the scope defaults to
 *    Master (see the mount effect below) and this page auto-redirects
 *    to `/dashboard` after a short delay — with an immediate "Go now"
 *    button for anyone who doesn't want to wait out the countdown.
 *  - One or more target roles: shows a "which role are you working on
 *    today?" prompt. Picking a role sets it as the active scope and
 *    continues to the dashboard; picking "Continue with Master Profile"
 *    (or simply navigating away via the nav rail without picking
 *    anything) leaves the scope at Master — the mount effect below
 *    proactively sets Master as the *default* the instant the roles
 *    list is known, so "didn't select anything" and "explicitly chose
 *    Master" resolve to the exact same outcome, per direct request.
 */
export function WelcomePage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const { data: quote } = useQuoteOfTheDay();
  const { data: targetRoles, isLoading } = useTargetRoles();
  const setActiveTargetRoleId = useTargetRoleScopeStore((state) => state.setActiveTargetRoleId);

  // Runs once, the first time targetRoles finishes loading — sets
  // Master as the working default before the person has made any
  // choice, so simply leaving this page (via the nav rail, or the
  // no-roles auto-redirect below) without picking a role still resolves
  // to Master rather than silently carrying over a stale scope from a
  // previous session.
  const hasAppliedDefaultRef = useRef(false);
  useEffect(() => {
    if (hasAppliedDefaultRef.current || targetRoles === undefined) return;
    hasAppliedDefaultRef.current = true;
    setActiveTargetRoleId(null);
  }, [targetRoles, setActiveTargetRoleId]);

  const hasNoTargetRoles = targetRoles !== undefined && targetRoles.length === 0;

  useEffect(() => {
    if (!hasNoTargetRoles) return;
    const timer = setTimeout(() => {
      navigate("/dashboard", { replace: true });
    }, NO_ROLES_REDIRECT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [hasNoTargetRoles, navigate]);

  function chooseRole(roleId: string | null) {
    setActiveTargetRoleId(roleId);
    navigate("/dashboard", { replace: true });
  }

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 px-4 py-10 text-center">
      <div className="flex flex-col items-center gap-3">
        <h1 className="font-display text-2xl font-semibold sm:text-3xl">
          Welcome back
          {user?.firstName ? `, ${user.firstName}` : ""}!
        </h1>
        {quote && (
          <p className="max-w-xl text-sm italic text-muted-foreground">
            "{quote.content}"{quote.author ? ` — ${quote.author}` : ""}
          </p>
        )}
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">Loading your profile...</p>}

      {hasNoTargetRoles && (
        <Card className="w-full max-w-md">
          <CardContent className="flex flex-col items-center gap-3 pt-6 text-center">
            <p className="text-sm text-muted-foreground">
              You haven't added any target roles yet — taking you to your dashboard...
            </p>
            <Button
              type="button"
              variant="primary"
              onClick={() => navigate("/dashboard", { replace: true })}
            >
              Go to Dashboard now
            </Button>
          </CardContent>
        </Card>
      )}

      {targetRoles && targetRoles.length > 0 && (
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Which role are you working on today?</CardTitle>
            <p className="text-sm text-muted-foreground">
              This sets the profile the rest of the app — AI Career Coach, Resume Intelligence,
              Opportunity Intelligence, Learning Intelligence, Interview Prep — focuses on until
              you change it.
            </p>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {targetRoles.map((role) => (
              <Button
                key={role.id}
                type="button"
                variant="outline"
                className="justify-start"
                onClick={() => chooseRole(role.id)}
              >
                <Badge variant="accent" className="mr-2 shrink-0">
                  {role.tag}
                </Badge>
                <span className="truncate">{role.role_name}</span>
              </Button>
            ))}
            <Button type="button" variant="ghost" onClick={() => chooseRole(null)}>
              Continue with Master Profile
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
