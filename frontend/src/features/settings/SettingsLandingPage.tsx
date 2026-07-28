import { Card, CardContent } from "@/components/ui/card";
import { Settings } from "lucide-react";

/**
 * Bare /settings landing — deliberately does not default into Profile
 * (or any other category). The Right Nav's Settings sub-nav is the only
 * way in, so this just points there rather than picking on the user's
 * behalf.
 */
export function SettingsLandingPage() {
  return (
    <Card className="max-w-xl">
      <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
        <Settings className="h-8 w-8 text-muted-foreground" strokeWidth={1.5} />
        <p className="text-sm text-muted-foreground">
          Choose a category from the panel on the right to set up your account — start with{" "}
          <span className="font-medium text-foreground">Profile</span>.
        </p>
      </CardContent>
    </Card>
  );
}
