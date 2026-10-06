// Display formats from .claude/rules/frontend.md: dates as DD MMM YYYY, money with Indian digit grouping.

const LEGAL_TZ = "Asia/Kolkata";

const dateFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: LEGAL_TZ,
});

/** Legal dates arrive as "YYYY-MM-DD" and must not shift a day in any browser timezone. */
export function formatLegalDate(isoDate: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!match) throw new Error(`Not a YYYY-MM-DD date: ${isoDate}`);
  const [, y, m, d] = match;
  // Noon UTC is the same calendar day in Asia/Kolkata (UTC+05:30).
  return dateFormatter.format(new Date(Date.UTC(Number(y), Number(m) - 1, Number(d), 12)));
}

const rupees = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });

/** Money is integer paise in the API (`*_paise`). 12345678 paise -> "₹1,23,456.78". */
export function formatPaise(paise: number): string {
  if (!Number.isInteger(paise)) throw new Error("paise must be an integer");
  return rupees.format(paise / 100);
}
