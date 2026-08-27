import { Card, CardContent } from "@/components/ui/card";
import { SETTINGS_NAV_ITEMS } from "@/lib/nav-items";
import { useMobileDropdownStore } from "@/stores/mobile-dropdown-store";
import { Link } from "react-router-dom";

/**
 * Bare /settings landing — a real card per category (icon, name, and its
 * one-line `purpose` from nav-items.ts). Profile, Platform Admin, and
 * Account (delete) moved to the platform Hub's own Settings
 * (2026-08-26) — only CCAI-specific categories remain here, so this no
 * longer needs any permission-based gating of its own.
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

  if (isMobileAccountMenuOpen) {
    return null;
  }

  return (
    <div className="grid max-w-xl gap-3">
      {SETTINGS_NAV_ITEMS.map(({ to, label, icon: Icon, purpose }) => (
        <Link key={to} to={to}>
          <Card className="transition-colors hover:border-accent/50 hover:bg-muted/40">
            <CardContent className="flex items-center gap-4 py-4">
              <Icon className="h-6 w-6 shrink-0 text-accent" strokeWidth={1.5} />
              <div className="min-w-0">
                <p className="text-sm font-semibold">{label}</p>
                <p className="text-sm text-muted-foreground">{purpose}</p>
              </div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
