import { AppShell } from "@/components/layout/AppShell";
import { CareerProfilePage } from "@/features/career-profile/CareerProfilePage";
import { CoachPage } from "@/features/coach/CoachPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { SettingsAIModelPage } from "@/features/settings/SettingsAIModelPage";
import { SettingsLandingPage } from "@/features/settings/SettingsLandingPage";
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
 * /login is outside ProtectedRoute (it IS the escape hatch for
 * unauthenticated visitors). Everything under AppShell requires a
 * session — see routes/ProtectedRoute.tsx.
 */
export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: "/",
        element: <AppShell />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: "profile", element: <CareerProfilePage /> },
          { path: "resumes", element: <ResumeIntelligencePage /> },
          { path: "skills", element: <SkillIntelligencePage /> },
          { path: "coach", element: <CoachPage /> },
          { path: "settings", element: <SettingsLandingPage /> },
          { path: "settings/profile", element: <SettingsProfilePage /> },
          { path: "settings/ai-model", element: <SettingsAIModelPage /> },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);
