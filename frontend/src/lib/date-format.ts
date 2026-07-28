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
