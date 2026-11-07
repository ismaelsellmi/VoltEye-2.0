const cache = new Map<number, Intl.NumberFormat>();

export function nf(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  if (!cache.has(digits)) cache.set(digits, new Intl.NumberFormat("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits }));
  return cache.get(digits)!.format(x);
}

export const pct = (x: number | null | undefined, digits = 1) => (x === null || x === undefined ? "–" : `${nf(x * 100, digits)} %`);

const dayFmt = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" });
const shortDay = new Intl.DateTimeFormat("fr-FR", { weekday: "short", day: "numeric", month: "short" });
const timeFmt = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export const fmtDay = (d: string) => dayFmt.format(new Date(d.length === 10 ? `${d}T12:00:00` : d));
export const fmtShortDay = (d: string) => shortDay.format(new Date(d.length === 10 ? `${d}T12:00:00` : d));
export const fmtTime = (d: string | number) => timeFmt.format(new Date(d));
