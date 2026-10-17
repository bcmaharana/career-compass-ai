import { cn } from "@/lib/utils";

export function TabStrip<T extends string | null>({
  tabs,
  activeId,
  onChange,
  ariaLabel,
  size = "md",
}: {
  tabs: readonly { id: T; label: string }[];
  activeId: T;
  onChange: (id: T) => void;
  ariaLabel: string;
  size?: "md" | "sm";
}) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="flex items-end gap-1 border-b border-muted-foreground/30"
    >
      {tabs.map((tab) => (
        <button
          key={tab.id ?? "__null__"}
          type="button"
          role="tab"
          aria-selected={activeId === tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            "relative -mb-px rounded-t-lg border border-b-0 font-medium transition-colors",
            size === "sm" ? "px-3 py-1 text-xs" : "px-4 py-2 text-sm",
            activeId === tab.id
              ? "border-border bg-card text-foreground"
              : "border-transparent text-muted-foreground hover:bg-muted/60 hover:text-foreground",
          )}
        >
          {tab.label}
          {activeId === tab.id && (
            <span className="absolute inset-x-0 -bottom-px h-0.5 bg-[linear-gradient(90deg,#a855f7_12.5%,#3b82f6_37.5%,#22c55e_58.33%,#fdba74_75%,#fca5a5_91.67%)]" />
          )}
        </button>
      ))}
    </div>
  );
}
