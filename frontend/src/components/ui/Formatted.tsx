import { formatDateTime, formatInterval, formatMinutes, formatMoney, formatPercent, formatRelative, isDemoClock } from "@/lib/format";
import { t } from "@/copy/t";
import { Tooltip } from "./Tooltip";

/** Relative within 7 days, with the exact date in the tooltip ("in the demo world" in demo mode). */
export function RelativeTime({ at }: { at: string | null | undefined }) {
  if (!at) return null;
  const exact = formatDateTime(at);
  return (
    <Tooltip content={isDemoClock() ? t("format.demoWorldDate", { date: exact }) : exact}>
      <time dateTime={at} tabIndex={0} className="tabular">
        {formatRelative(at)}
      </time>
    </Tooltip>
  );
}

export const Money = ({ usd, fine }: { usd: number | null | undefined; fine?: boolean }) => <span className="tabular">{formatMoney(usd, fine)}</span>;
export const Minutes = ({ minutes }: { minutes: number | null | undefined }) => <span className="tabular">{formatMinutes(minutes)}</span>;
export const Percent = ({ value }: { value: number | null | undefined }) => <span className="tabular">{formatPercent(value)}</span>;
export const Interval = ({ low, high }: { low: number | null | undefined; high: number | null | undefined }) => {
  const s = formatInterval(low, high);
  return s ? <span className="tabular text-muted">{s}</span> : null;
};
