import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useId } from "react";

export function ContentColumnAppearanceControls({
  showBackground,
  backgroundColor,
  onShowBackgroundChange,
  onBackgroundColorChange,
}: {
  showBackground: boolean;
  backgroundColor: string | null;
  onShowBackgroundChange: (show: boolean) => void;
  onBackgroundColorChange: (color: string | null) => void;
}) {
  const colorInputId = useId();

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <div className="flex items-center gap-2">
        <Switch
          checked={showBackground}
          onCheckedChange={onShowBackgroundChange}
          label="Show background"
        />
        <span className="text-sm font-medium leading-none">Show background</span>
      </div>
      {showBackground && (
        <div className="flex items-center gap-2">
          <Label htmlFor={colorInputId}>Background color</Label>
          <Input
            id={colorInputId}
            type="color"
            value={backgroundColor ?? "#ffffff"}
            onChange={(event) => onBackgroundColorChange(event.target.value)}
            className="h-9 w-12 cursor-pointer p-1"
            aria-label="Background color"
          />
          {backgroundColor && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onBackgroundColorChange(null)}
            >
              Default
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
