import { usePlatformAdminMe } from "@/api/queries/platform-admin";
import { Card, CardContent } from "@/components/ui/card";
import { SETTINGS_NAV_ITEMS, STANDARD_SETTINGS_NAV_ITEMS } from "@/lib/nav-items";
import { cn } from "@/lib/utils";
import { useMobileDropdownStore } from "@/stores/mobile-dropdown-store";
import { Link } from "react-router-dom";

/**
 * Bare /settings landing — a real card per category (icon, name, and its
 * one-line `purpose` from nav-items.ts) rather than the earlier plain
 * "pick a category" instructional card, direct 2026-08-20 request. Still
 * deliberately doesn't default straight into Profile — this page IS the
 * chooser now, just a clickable one instead of a passive message; the
 * Right Nav's Settings sub-nav remains the other way in on desktop.
 *
 * Platform Admin only gets a card for a caller who actually has at least
 * one platform.* permission — same gate AccountPanelContent.tsx's own
 * sub-nav already applies, so this page never shows a card that would
 * just 403.
 *
 * Renders nothing at all while the mobile account dropdown is open
 * (`useMobileDropdownStore`) — see the previous version of this
 * docstring for why: on a narrow viewport its opaque panel covers most
 * of the page width, and rendering this page's own cards underneath it
 * at the same time left them showing beside/behind the dropdown for no
 * reason. The cards still show normally on desktop (the store's `active`
 * never becomes `"account"` there), and on mobile once the dropdown has
 * been dismissed without a category chosen.
 */
export function SettingsLandingPage() {
  const isMobileAccountMenuOpen = useMobileDropdownStore((state) => state.active === "account");
  const { data: platformAdmin } = usePlatformAdminMe();

  if (isMobileAccountMenuOpen) {
    return null;
  }

  const visibleItems =
    platformAdmin && platformAdmin.permission_codes.length > 0
      ? SETTINGS_NAV_ITEMS
      : STANDARD_SETTINGS_NAV_ITEMS;

  return (
    <div className="grid max-w-xl gap-3">
      {visibleItems.map(({ to, label, icon: Icon, purpose }) => {
        // Account (delete-your-account) is styled as a deliberate warning
        // card — solid destructive red with white text — so it visually
        // stands apart from every other, non-destructive settings category,
        // on top of always sorting last per nav-items.ts's own ordering.
        const isAccount = to === "/settings/account";
        return (
          <Link key={to} to={to}>
            <Card
              className={cn(
                "transition-colors",
                isAccount
                  ? "border-destructive bg-destructive hover:bg-destructive/90"
                  : "hover:border-accent/50 hover:bg-muted/40",
              )}
            >
              <CardContent className="flex items-center gap-4 py-4">
                <Icon
                  className={cn(
                    "h-6 w-6 shrink-0",
                    isAccount ? "text-destructive-foreground" : "text-accent",
                  )}
                  strokeWidth={1.5}
                />
                <div className="min-w-0">
                  <p
                    className={cn(
                      "text-sm font-semibold",
                      isAccount && "text-destructive-foreground",
                    )}
                  >
                    {label}
                  </p>
                  <p
                    className={cn(
                      "text-sm",
                      isAccount ? "text-destructive-foreground/85" : "text-muted-foreground",
                    )}
                  >
                    {purpose}
                  </p>
                </div>
              </CardContent>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
