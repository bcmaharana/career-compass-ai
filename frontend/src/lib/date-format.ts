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
