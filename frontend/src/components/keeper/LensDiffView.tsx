import { Link } from "react-router";
import { Minus, Pencil, Plus } from "lucide-react";
import type { LensDiff, LensDiffEntry } from "@/api/types";
import { Markdown } from "@/components/ui/Markdown";
import { Badge } from "@/components/ui/Badge";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { humanise } from "@/lib/format";
import { isObj } from "@/lib/unknown";

function show(v: unknown): string {
  if (v === null || v === undefined) return t("format.none");
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

function Entry({ e, kind }: { e: LensDiffEntry; kind: "added" | "removed" | "changed" }) {
  const fields = Object.entries(e.fields ?? {});
  return (
    <li className={cx("rounded-md border p-2.5 text-sm", kind === "added" ? "border-edge-border bg-edge-bg/40" : "border-border")}>
      <div className="flex flex-wrap items-center gap-2">
        {kind === "added" ? <Plus className="size-4 text-success" aria-hidden /> : kind === "removed" ? <Minus className="size-4 text-danger" aria-hidden /> : <Pencil className="size-4 text-muted" aria-hidden />}
        <Link to={`/lens?tab=items&item=${encodeURIComponent(e.item_id)}`} className={cx("font-medium hover:underline", kind === "removed" && "line-through")}>
          {e.title}
        </Link>
        <span className="text-xs text-muted">{e.category}</span>
      </div>
      {e.detail ? <p className="mt-1 text-muted">{e.detail}</p> : null}
      {fields.length ? (
        <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
          {fields.map(([name, v]) => {
            const o = isObj(v) ? v : {};
            return (
              <div key={name} className="contents">
                <dt className="text-muted">{humanise(name)}</dt>
                <dd className="k-anywhere">
                  <span className="line-through opacity-70">{show(o.from)}</span> → <span className="font-medium">{show(o.to)}</span>
                </dd>
              </div>
            );
          })}
        </dl>
      ) : null}
    </li>
  );
}

/** The summary bullets, then Added, Removed and Changed (field-level before/after). */
export function LensDiffView({ diff }: { diff: LensDiff }) {
  const groups = [
    { key: "added" as const, items: diff.added, title: t("lensDiff.added", { n: diff.added.length }) },
    { key: "removed" as const, items: diff.removed, title: t("lensDiff.removed", { n: diff.removed.length }) },
    { key: "changed" as const, items: diff.changed, title: t("lensDiff.changed", { n: diff.changed.length }) },
  ];
  return (
    <div className="space-y-4">
      <div className="rounded-md bg-surface-2 p-3">
        <div className="mb-1 flex items-center gap-2">
          <p className="text-sm font-semibold">{t("lensDiff.summary", { from: diff.from_version, to: diff.to_version })}</p>
          {diff.summary_simulated ? <Badge tone="warning">{t("lensDiff.simulated")}</Badge> : null}
        </div>
        <Markdown source={diff.summary_md} className="text-sm" />
      </div>
      {groups.map((g) => (
        <section key={g.key} aria-label={g.title}>
          <h4 className="mb-1.5 text-sm font-semibold">{g.title}</h4>
          {g.items.length ? (
            <ul className="space-y-1.5">
              {g.items.map((e) => (
                <Entry key={e.item_id} e={e} kind={g.key} />
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">{t("common.none")}</p>
          )}
        </section>
      ))}
    </div>
  );
}
