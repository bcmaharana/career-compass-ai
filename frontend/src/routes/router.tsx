import { AppShell } from "@/components/layout/AppShell";
import { CareerProfilePage } from "@/features/career-profile/CareerProfilePage";
import { CoachPage } from "@/features/coach/CoachPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { VerifyEmailPage } from "@/features/auth/VerifyEmailPage";
import { LandingPage } from "@/features/landing/LandingPage";
import { SignupPage } from "@/features/landing/SignupPage";
import { PrivacyPolicyPage } from "@/features/legal/PrivacyPolicyPage";
import { TermsOfServicePage } from "@/features/legal/TermsOfServicePage";
import { SettingsAIModelPage } from "@/features/settings/SettingsAIModelPage";
import { SettingsAccountPage } from "@/features/settings/SettingsAccountPage";
import { SettingsLandingPage } from "@/features/settings/SettingsLandingPage";
import { SettingsPlatformAdminPage } from "@/features/settings/SettingsPlatformAdminPage";
import { SettingsProfilePage } from "@/features/settings/SettingsProfilePage";
import { ResumeIntelligencePage } from "@/features/resume-intelligence/ResumeIntelligencePage";
import { NotFoundPage } from "@/routes/NotFound";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { SkillIntelligencePage } from "@/features/skill-intelligence/SkillIntelligencePage";
import { createBrowserRouter } from "react-router-dom";

/**
 * Route tree. Feature modules add their own routes here as they land
 * (Phase 2 onward) — this file stays the single source of truth for the
 * app's URL structure, rather than routes being registered ad hoc from
 * inside feature components.
 *
 * "/" is the public landing page, "/login" and "/signup" are the other
 * unauthenticated entry points — none of the three sit under
 * ProtectedRoute. Everything under AppShell (now at /dashboard and
 * beyond) requires a session — see routes/ProtectedRoute.tsx, which
 * redirects an unauthenticated visitor to "/" (the pitch), not straight
 * to the login form.
 */
export const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/forgot-password",
    element: <ForgotPasswordPage />,
  },
  {
    path: "/reset-password",
    element: <ResetPasswordPage />,
  },
  {
    path: "/signup",
    element: <SignupPage />,
  },
  {
    path: "/verify-email",
    element: <VerifyEmailPage />,
  },
  {
    path: "/terms",
    element: <TermsOfServicePage />,
  },
  {
    path: "/privacy",
    element: <PrivacyPolicyPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "dashboard", element: <DashboardPage /> },
          { path: "profile", element: <CareerProfilePage /> },
          { path: "resumes", element: <ResumeIntelligencePage /> },
          { path: "skills", element: <SkillIntelligencePage /> },
          { path: "coach", element: <CoachPage /> },
          { path: "settings", element: <SettingsLandingPage /> },
          { path: "settings/profile", element: <SettingsProfilePage /> },
          { path: "settings/ai-model", element: <SettingsAIModelPage /> },
          { path: "settings/account", element: <SettingsAccountPage /> },
          { path: "settings/platform-admin", element: <SettingsPlatformAdminPage /> },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);
