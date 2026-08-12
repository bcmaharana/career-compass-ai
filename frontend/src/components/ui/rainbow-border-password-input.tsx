import { RainbowBorderInput } from "@/components/ui/rainbow-border-input";
import { cn } from "@/lib/utils";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import type { ComponentProps } from "react";

type Props = Omit<ComponentProps<typeof RainbowBorderInput>, "type">;

/**
 * RainbowBorderInput plus a show/hide toggle — every password field in the
 * app (LoginPage, SignupPage's personal + enterprise forms) needs the same
 * eye-icon affordance, so it lives here once rather than five times.
 */
export function RainbowBorderPasswordInput({ className, ...props }: Props) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <RainbowBorderInput
        type={visible ? "text" : "password"}
        className={cn("pr-10", className)}
        {...props}
      />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        className="absolute inset-y-0 right-2 flex items-center text-muted-foreground hover:text-foreground"
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}
