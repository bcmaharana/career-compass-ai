import { formatDisplayDate } from "@/lib/date-format";

/** "Last logged in @ 12:30pm ET on Sunday, 26-Jul-2026" — always the
 * *viewer's* local time/timezone, not a fixed zone, matching every other
 * local-time display in this shell (see AccountPanelContent's
 * useLocalClock). Shared by DesktopShell.tsx's Left Nav bottom box and
 * AppFooter.tsx's mobile-only clock column — both show the same fact,
 * just in a rail vs. a footer icon's tooltip. */
export function formatLastLogin(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  const time = date
    .toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", hour12: true })
    .toLowerCase()
    .replace(" ", "");
  const tzAbbr =
    new Intl.DateTimeFormat(undefined, { timeZoneName: "short" })
      .formatToParts(date)
      .find((part) => part.type === "timeZoneName")?.value ?? "";
  const weekday = date.toLocaleDateString(undefined, { weekday: "long" });
  const isoDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  return `Last logged in @ ${time} ${tzAbbr} on ${weekday}, ${formatDisplayDate(isoDate)}`;
}
