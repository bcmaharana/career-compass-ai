import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { ComponentProps } from "react";

/**
 * A normal-width (1px) rainbow border — the gradient-padding trick from
 * card borders elsewhere, just with 1px of padding instead of 6px, so it
 * reads as "recolored border" rather than "thick frame." border-image
 * would be the more obvious CSS tool for a gradient border, but it
 * doesn't respect border-radius, so it'd square off Input's rounded
 * corners — this nested-box approach doesn't have that problem at any
 * thickness.
 *
 * Extracted here (not left inline in LoginPage.tsx) once a second and
 * third unauthenticated form — ForgotPasswordPage, ResetPasswordPage —
 * needed the exact same input styling.
 */
export function RainbowBorderInput({ className, ...props }: ComponentProps<typeof Input>) {
  return (
    <div className="rounded-md bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)] p-px">
      <Input {...props} className={cn("border-0", className)} />
    </div>
  );
}
