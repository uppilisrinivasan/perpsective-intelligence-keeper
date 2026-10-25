import { Link } from "react-router";
import type { RoutedFinding } from "@/api/types";
import { Disclosure } from "@/components/ui/Disclosure";
import { t } from "@/copy/t";
import { formatDate } from "@/lib/format";
import { LensItemChip } from "./LensItem";

type Evidence = RoutedFinding["evidence"];

/** Quotes with links: the lens items and past comments behind a claim ("Because {name} said this on #{n}"). */
export function EvidenceList({ evidence, maintainer, lane }: { evidence: Evidence; maintainer: string; lane: string }) {
  const items = evidence.lens_items ?? [];
  const comments = evidence.past_comments ?? [];
  const blind = evidence.blind_spot_item;
  const prs = [...new Set(comments.map((c) => c.pr_number))];
  return (
    <div className="space-y-1.5 text-sm">
      {items.length > 0 ? (
        <p className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted">{t("finding.why.pattern", { name: maintainer, n: items.length })}</span>
          {items.map((it) => (
            <LensItemChip key={it.id} item={it} />
          ))}
        </p>
      ) : null}
      {lane === "blind_spot" && blind ? (
        <p className="text-muted">
          {t("finding.why.blindSpot", { name: maintainer, ignored: blind.ignored ?? 0, bad: blind.bad_outcomes ?? 0, title: blind.title })}
          {blind.outcome_prs?.length ? (
            <span className="ml-1">
              {blind.outcome_prs.slice(0, 4).map((n) => (
                <Link key={n} className="mr-1 text-primary hover:underline" to={`/pr/${n}`}>
                  {t("format.prNumber", { n })}
                </Link>
              ))}
            </span>
          ) : null}
        </p>
      ) : null}
      {evidence.baseline_pair ? <p className="text-muted">{t("finding.why.baseline", { statement: evidence.baseline_pair.statement })}</p> : null}
      {evidence.why_similar ? <p className="text-muted">{evidence.why_similar}</p> : null}
      {comments.length > 0 ? (
        <Disclosure summary={<span className="text-muted">{t("finding.why.comments", { name: maintainer, prs: prs.map((n) => `#${n}`).join(", "), n: comments.length })}</span>}>
          <ul className="space-y-2">
            {comments.map((c) => (
              <li key={c.id} className="border-l-2 border-edge-border pl-3">
                <blockquote className="text-sm k-anywhere">{c.excerpt}</blockquote>
                <p className="mt-0.5 text-xs text-muted">
                  {c.author ? `${c.author} · ` : ""}
                  <Link to={`/pr/${c.pr_number}`} className="text-primary hover:underline">
                    {t("format.prNumber", { n: c.pr_number })}
                  </Link>
                  {c.path ? ` · ${c.path}` : ""}
                  {c.at ? ` · ${formatDate(c.at)}` : ""}
                </p>
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
    </div>
  );
}
