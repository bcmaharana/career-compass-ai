import { cn } from "@/lib/utils";
import { forwardRef } from "react";
import type { LabelHTMLAttributes } from "react";

export const Label = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn("text-sm font-medium leading-none peer-disabled:opacity-70", className)}
      {...props}
    />
  ),
);
Label.displayName = "Label";
