import { useCallback, useLayoutEffect, useMemo, useState } from "react";
import { ArrowRight } from "lucide-react";
import type { ComparePair, FindingOut, HumanPair } from "@/api/types";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { useContainerWidth, remToPx } from "@/lib/useContainerWidth";
import { laneDef, laneLabel } from "@/lib/lanes";
import { LaneDot, LaneIcon } from "./Lane";

export interface CompareViewProps {
  baseline: FindingOut[];
  lens: FindingOut[];
  pairs: ComparePair[];
  residual?: { r_plus?: string[]; r_minus?: string[] };
  human?: FindingOut[] | null;
  humanPairs?: HumanPair[];
  maintainer: string;
  onOpenFinding?: (id: string) => void;
}

const NO_MATCH = new Set(["no_match", "none", "unmatched", "different"]);
function isMatch(decision: string | null | undefined): boolean {
  return !NO_MATCH.has((decision ?? "").toLowerCase());
}

/** Lane colour for each card in Compare: matched = shared, lens-only = edge, baseline R− = blind spot. */
export function compareLanes(props: Pick<CompareViewProps, "baseline" | "lens" | "pairs" | "residual">) {
  const matched = props.pairs.filter((p) => isMatch(p.decision));
  const lensMatched = new Set(matched.map((p) => p.lens_id));
  const baseMatched = new Set(matched.map((p) => p.baseline_id));
  const rPlus = new Set(props.residual?.r_plus ?? []);
  const rMinus = new Set(props.residual?.r_minus ?? []);
  const lane = new Map<string, string>();
  for (const f of props.lens) lane.set(f.id, lensMatched.has(f.id) && !rPlus.has(f.id) ? "shared" : "edge");
  for (const f of props.baseline) lane.set(f.id, baseMatched.has(f.id) ? "shared" : rMinus.has(f.id) ? "blind_spot" : "baseline_only");
  const edge = props.lens.filter((f) => lane.get(f.id) === "edge").length;
  const blind = props.baseline.filter((f) => lane.get(f.id) === "blind_spot").length;
  return { lane, matched, edge, blind };
}

function CompareCard({ f, lane, onOpen, tour }: { f: FindingOut; lane: string; onOpen?: (id: string) => void; tour?: boolean }) {
  const def = laneDef(lane);
  const where = f.anchor.path ? (f.anchor.start_line ? t("format.pathLine", { path: f.anchor.path, line: f.anchor.start_line }) : f.anchor.path) : null;
  return (
    <article
      data-cmp={f.id}
      data-tour={tour ? "compare_pair" : undefined}
      data-tour-id={tour ? f.id : undefined}
      className={cx("rounded-md border border-l-4 bg-surface p-2.5 text-sm", def.border, "border-y-border border-r-border")}
    >
      <div className="flex items-start gap-1.5">
        <LaneIcon lane={lane} className="mt-0.5" />
        <h4 className="min-w-0 flex-1 font-medium leading-snug k-anywhere">{f.title}</h4>
      </div>
      <p className="mt-1 text-xs text-muted">
        <span className="sr-only">{laneLabel(lane)} · </span>
        {f.category_label || f.category}
        {where ? <span className="font-mono k-anywhere"> · {where}</span> : null}
      </p>
      {f.statement && f.statement !== f.title ? <p className="mt-1 text-xs text-muted line-clamp-3 k-anywhere">{f.statement}</p> : null}
      {onOpen ? (
        <button type="button" onClick={() => onOpen(f.id)} className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
          {t("compare.openInDiff")}
          <ArrowRight className="size-3" aria-hidden />
        </button>
      ) : null}
    </article>
  );
}

interface Line {
  key: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  lane: string;
}

/** Baseline vs lens (plus "What {maintainer} actually wrote"), with SVG connectors between matched pairs. */
export function CompareView(props: CompareViewProps) {
  const { baseline, lens, human, maintainer, onOpenFinding } = props;
  const humanPairs = useMemo(() => props.humanPairs ?? [], [props.humanPairs]);
  const { lane, matched, edge, blind } = useMemo(() => compareLanes({ baseline, lens, pairs: props.pairs, residual: props.residual }), [baseline, lens, props.pairs, props.residual]);
  const [ref, width] = useContainerWidth<HTMLDivElement>();
  const stacked = width > 0 && width < remToPx(48);
  const [lines, setLines] = useState<Line[]>([]);
  const showHuman = Array.isArray(human);
  const lensHuman = useMemo(() => humanPairs.filter((p) => p.system === "lens" && isMatch(p.decision)), [humanPairs]);

  // Order: matched baseline rows first (aligned with their lens partners), then the rest.
  const lensOrdered = useMemo(() => {
    const byBase = new Map(matched.map((p) => [p.baseline_id, p.lens_id]));
    const order: FindingOut[] = [];
    const seen = new Set<string>();
    for (const b of baseline) {
      const lid = byBase.get(b.id);
      const lf = lid ? lens.find((x) => x.id === lid) : undefined;
      if (lf && !seen.has(lf.id)) {
        order.push(lf);
        seen.add(lf.id);
      }
    }
    for (const f of lens) if (!seen.has(f.id)) order.push(f);
    return order;
  }, [baseline, lens, matched]);

  const recompute = useCallback(() => {
    const root = ref.current;
    if (!root || stacked) {
      setLines((prev) => (prev.length ? [] : prev));
      return;
    }
    const box = root.getBoundingClientRect();
    const rect = (id: string, col: string) => root.querySelector(`[data-col="${col}"] [data-cmp="${CSS.escape(id)}"]`)?.getBoundingClientRect();
    const out: Line[] = [];
    for (const p of matched) {
      const a = rect(p.baseline_id, "baseline");
      const b = rect(p.lens_id, "lens");
      if (a && b) out.push({ key: `${p.baseline_id}-${p.lens_id}`, x1: a.right - box.left, y1: a.top + a.height / 2 - box.top, x2: b.left - box.left, y2: b.top + b.height / 2 - box.top, lane: "shared" });
    }
    for (const p of lensHuman) {
      const a = rect(p.other_id, "lens");
      const b = rect(p.human_id, "human");
      if (a && b) out.push({ key: `${p.other_id}-${p.human_id}`, x1: a.right - box.left, y1: a.top + a.height / 2 - box.top, x2: b.left - box.left, y2: b.top + b.height / 2 - box.top, lane: lane.get(p.other_id) ?? "edge" });
    }
    setLines((prev) => (JSON.stringify(prev) === JSON.stringify(out) ? prev : out));
  }, [ref, stacked, matched, lensHuman, lane]);

  useLayoutEffect(() => {
    recompute();
    const root = ref.current;
    if (!root || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => recompute());
    ro.observe(root);
    root.querySelectorAll("[data-cmp]").forEach((el) => ro.observe(el));
    return () => ro.disconnect();
  }, [recompute, ref, baseline, lens, human]);

  const titleOf = (id: string) => [...baseline, ...lens, ...(human ?? [])].find((f) => f.id === id)?.title ?? id;

  return (
    <div className="space-y-4">
      <p className="text-base">
        {t("compare.sentence", { b: baseline.length, edge, blind, name: maintainer })}
      </p>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label={t("compare.legend")}>
        {["edge", "blind_spot", "shared", "baseline_only"].map((l) => (
          <li key={l} className="inline-flex items-center gap-1.5">
            <LaneDot lane={l} />
            <LaneIcon lane={l} />
            {t(`compare.legend.${l}` as "compare.legend.edge", { name: maintainer })}
          </li>
        ))}
      </ul>
      <div ref={ref} className="relative">
        <div className={cx("grid gap-x-10 gap-y-4", stacked ? "grid-cols-1" : showHuman ? "grid-cols-3" : "grid-cols-2")}>
          <section data-col="baseline" aria-labelledby="cmp-baseline" className="space-y-2.5">
            <h3 id="cmp-baseline" className="text-sm font-semibold text-muted">
              {t("compare.col.baseline")}
            </h3>
            {baseline.length ? baseline.map((f) => <CompareCard key={f.id} f={f} lane={lane.get(f.id) ?? "baseline_only"} onOpen={onOpenFinding} />) : <p className="text-sm text-muted">{t("compare.empty.baseline")}</p>}
          </section>
          <section data-col="lens" aria-labelledby="cmp-lens" className="space-y-2.5">
            <h3 id="cmp-lens" className="text-sm font-semibold text-muted">
              {t("compare.col.lens", { name: maintainer })}
            </h3>
            {lensOrdered.length ? (
              lensOrdered.map((f) => <CompareCard key={f.id} f={f} lane={lane.get(f.id) ?? "edge"} onOpen={onOpenFinding} tour={lane.get(f.id) === "edge"} />)
            ) : (
              <p className="text-sm text-muted">{t("compare.empty.lens")}</p>
            )}
          </section>
          {showHuman ? (
            <section data-col="human" data-tour="human_column" aria-labelledby="cmp-human" className="space-y-2.5">
              <h3 id="cmp-human" className="text-sm font-semibold text-muted">
                {t("compare.col.human", { name: maintainer })}
              </h3>
              {human && human.length ? human.map((f) => <CompareCard key={f.id} f={f} lane="unsorted" />) : <p className="text-sm text-muted">{t("compare.empty.human", { name: maintainer })}</p>}
            </section>
          ) : null}
        </div>
        {!stacked && lines.length ? (
          <svg className="pointer-events-none absolute inset-0 size-full overflow-visible" aria-hidden>
            {lines.map((l) => {
              const mx = (l.x1 + l.x2) / 2;
              return <path key={l.key} d={`M ${l.x1} ${l.y1} C ${mx} ${l.y1}, ${mx} ${l.y2}, ${l.x2} ${l.y2}`} fill="none" strokeWidth={1.5} className={l.lane === "shared" ? "stroke-shared-solid" : "stroke-edge-solid"} />;
            })}
          </svg>
        ) : null}
      </div>
      {matched.length || lensHuman.length ? (
        <div className={cx("text-sm", !stacked && "sr-only")}>
          <p className="font-medium">{t("compare.matches")}</p>
          <ul className="list-disc pl-5 text-muted">
            {matched.map((p) => (
              <li key={`${p.baseline_id}-${p.lens_id}`}>{t("compare.matchLine", { a: titleOf(p.baseline_id), b: titleOf(p.lens_id) })}</li>
            ))}
            {lensHuman.map((p) => (
              <li key={`${p.other_id}-${p.human_id}`}>{t("compare.matchHuman", { a: titleOf(p.other_id), b: titleOf(p.human_id), name: maintainer })}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
