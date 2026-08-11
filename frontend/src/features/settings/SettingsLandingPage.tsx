import { Card, CardContent } from "@/components/ui/card";
import { useMobileDropdownStore } from "@/stores/mobile-dropdown-store";
import { Settings } from "lucide-react";

/**
 * Bare /settings landing — deliberately does not default into Profile
 * (or any other category). The Right Nav's Settings sub-nav is the only
 * way in on desktop; on mobile, MobileAccountMenu.tsx auto-opens its
 * dropdown on landing here for the same reason (see its own docstring).
 *
 * Renders nothing at all while that mobile dropdown is open
 * (`useMobileDropdownStore`) — on a narrow viewport its opaque panel
 * covers most of the page width, and rendering this page's own card
 * underneath it at the same time left an empty-looking blank card
 * showing beside/behind the dropdown for no reason once the message
 * inside it was hidden. The card (with its full instructional message)
 * still shows normally on desktop, where the store's `active` never
 * becomes `"account"` (MobileAccountMenu never mounts outside the mobile
 * shell), and on mobile once the dropdown has been dismissed without a
 * category chosen — at that point it's the only remaining way to explain
 * how to reopen it.
 */
export function SettingsLandingPage() {
  const isMobileAccountMenuOpen = useMobileDropdownStore((state) => state.active === "account");

  if (isMobileAccountMenuOpen) {
    return null;
  }

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
