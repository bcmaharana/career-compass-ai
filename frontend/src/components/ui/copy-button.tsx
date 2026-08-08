import { Button } from "@/components/ui/button";
import type { ButtonProps } from "@/components/ui/button";
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";
import { Check, Copy } from "lucide-react";

interface CopyButtonProps {
  /** Text copied verbatim on click — callers join lists themselves
   * (e.g. `skills.join(", ")`) so this component stays format-agnostic. */
  text: string;
  label?: string;
  disabled?: boolean;
  className?: string;
  /** Defaults to "outline" (this component's original look — Dashboard's
   * System Status "Copy fix" button, SystemStatusCard.tsx, relies on
   * this default and is unaffected). Skill Intelligence's Copy buttons
   * pass "ghost" instead, to match that page's buttons all being
   * invisible-by-default/hover-to-reveal, same as every other button
   * there. */
  variant?: ButtonProps["variant"];
}

/** Small button that copies `text` to the clipboard, swapping to a
 * checkmark + "Copied" for a moment as feedback. */
export function CopyButton({
  text,
  label = "Copy",
  disabled,
  className,
  variant = "outline",
}: CopyButtonProps) {
  const { copy, copied } = useCopyToClipboard();

  return (
    <Button
      type="button"
      variant={variant}
      size="sm"
      disabled={disabled || !text}
      onClick={() => copy(text)}
      className={className}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? "Copied" : label}
    </Button>
  );
}
