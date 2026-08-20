const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/**
 * Formats an ISO date string (yyyy-mm-dd, as the API sends and receives)
 * as dd-mmm-yyyy for display — e.g. "2026-04-04" -> "04-Apr-2026".
 *
 * Display-only: `<input type="date">` fields still use the browser's
 * native yyyy-mm-dd editing format (that's a native control, not
 * something CSS/JS can restyle without replacing it with a custom date
 * picker) — this formats dates everywhere they're *shown*, not edited.
 */
export function formatDisplayDate(isoDate: string | null | undefined): string | null {
  if (!isoDate) return null;

  const [year, month, day] = isoDate.split("-");
  const monthIndex = Number(month) - 1;
  if (!year || !day || monthIndex < 0 || monthIndex > 11) return isoDate;

  return `${day}-${MONTHS[monthIndex]}-${year}`;
}

/**
 * Formats a full ISO datetime string as dd-mmm-yyyy, h:mm AM/PM in the
 * viewer's local timezone — used where two records can land close
 * enough together that the date alone can't tell them apart (e.g.
 * Resume History, where several upload attempts within the same
 * minute/hour are a real, expected case — see ResumeIntelligencePage.tsx).
 */
export function formatDisplayDateTime(isoDateTime: string | null | undefined): string | null {
  if (!isoDateTime) return null;

  const date = new Date(isoDateTime);
  if (Number.isNaN(date.getTime())) return isoDateTime;

  const day = String(date.getDate()).padStart(2, "0");
  const month = MONTHS[date.getMonth()];
  const year = date.getFullYear();
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const hours24 = date.getHours();
  const hours12 = hours24 % 12 || 12;
  const ampm = hours24 >= 12 ? "PM" : "AM";

  return `${day}-${month}-${year}, ${hours12}:${minutes} ${ampm}`;
}

/**
 * "5 minutes ago"/"2 hours ago"/"yesterday"/"3 days ago" style relative
 * time — used where a persisted timestamp needs to read as clearly
 * historical, not live. Built specifically for JD Tailoring's
 * `tailored_resume_error`: that message can bake in a real-time-only
 * hint from the provider (e.g. "Try again in about 25 seconds"), which
 * reads as actively wrong once actually re-displayed minutes, hours, or
 * days later with no indication of when the underlying attempt actually
 * happened (confirmed live, 2026-08-20 — a genuine user report of a
 * "stale" rate-limit message that survived multiple logout/login
 * cycles, since it's real persisted session state, not transient UI).
 * Falls back to the absolute formatDisplayDateTime beyond a week, where
 * "N days ago" stops being more useful than a real date.
 */
export function formatRelativeTime(isoDateTime: string | null | undefined): string | null {
  if (!isoDateTime) return null;

  const date = new Date(isoDateTime);
  if (Number.isNaN(date.getTime())) return isoDateTime;

  const diffSeconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (diffSeconds < 0) return "just now"; // clock skew guard
  if (diffSeconds < 60) return "just now";
  const diffMinutes = Math.round(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
  return formatDisplayDateTime(isoDateTime);
}
