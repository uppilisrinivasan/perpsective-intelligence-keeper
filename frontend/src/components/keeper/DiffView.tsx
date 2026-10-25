import { Fragment, memo, useMemo, useRef, useState, type ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ChevronDown, ChevronRight, FileCode, Plus } from "lucide-react";
import type { DiffFile, RoutedFinding } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { parsePatch, toSplitRows, type DiffLine } from "@/lib/diff";

/** Above this many lines a file's rows are virtualised (component catalog: > 1,000 lines). */
const VIRTUAL_THRESHOLD = 1000;
/** Patches above this many lines show "Large diff: load anyway" first (screens/02 §4). */
const LARGE_THRESHOLD = 3000;

export interface DiffViewProps {
  files: DiffFile[];
  findings?: RoutedFinding[];
  mode?: "review" | "practice";
  wrap?: boolean;
  split?: boolean;
  renderFinding?: (f: RoutedFinding) => ReactNode;
  /** Practice: click the gutter to add a note on a line. */
  onLineClick?: (path: string, line: number) => void;
  renderNote?: (path: string, line: number) => ReactNode;
  noteLines?: Set<string>;
  onLoadLarge?: (filename: string) => void;
  flash?: { path: string; line: number | null } | null;
  collapsedByDefault?: boolean;
}

export function lineAnchorId(path: string, line: number): string {
  return `L-${encodeURIComponent(path)}-${line}`;
}
export function fileAnchorId(path: string): string {
  return `F-${encodeURIComponent(path)}`;
}

interface Slots {
  byLine: Map<number, RoutedFinding[]>;
  byOldLine: Map<number, RoutedFinding[]>;
  fileLevel: RoutedFinding[];
}

function slotFindings(path: string, findings: RoutedFinding[] | undefined, lines: DiffLine[]): Slots {
  const byLine = new Map<number, RoutedFinding[]>();
  const byOldLine = new Map<number, RoutedFinding[]>();
  const fileLevel: RoutedFinding[] = [];
  const newLines = new Set(lines.map((l) => l.newNo).filter((n): n is number => n !== null));
  const oldLines = new Set(lines.map((l) => l.oldNo).filter((n): n is number => n !== null));
  for (const f of findings ?? []) {
    if (f.anchor.path !== path) continue;
    const line = f.anchor.end_line ?? f.anchor.start_line;
    const left = (f.anchor.side ?? "RIGHT").toUpperCase() === "LEFT";
    if (f.anchor.scope === "file" || line === null || line === undefined) {
      fileLevel.push(f);
    } else if (left && oldLines.has(line)) {
      byOldLine.set(line, [...(byOldLine.get(line) ?? []), f]);
    } else if (!left && newLines.has(line)) {
      byLine.set(line, [...(byLine.get(line) ?? []), f]);
    } else {
      fileLevel.push(f);
    }
  }
  return { byLine, byOldLine, fileLevel };
}

function lineAria(l: DiffLine): string {
  if (l.kind === "add") return t("diff.addedLine", { n: l.newNo ?? "" });
  if (l.kind === "del") return t("diff.removedLine", { n: l.oldNo ?? "" });
  return t("diff.line", { n: l.newNo ?? "" });
}

const rowTone: Record<string, string> = {
  add: "bg-diff-add",
  del: "bg-diff-del",
  ctx: "",
  hunk: "bg-diff-hunk text-muted",
};
const gutterTone: Record<string, string> = {
  add: "bg-diff-add-gutter",
  del: "bg-diff-del-gutter",
  ctx: "bg-surface",
  hunk: "bg-diff-hunk",
};

function Gutter({ line, path, onLineClick, isNote }: { line: DiffLine; path: string; onLineClick?: (path: string, line: number) => void; isNote?: boolean }) {
  const n = line.newNo;
  return (
    <th
      scope="row"
      className={cx("sticky left-0 z-[1] select-none whitespace-nowrap px-2 text-right align-top font-normal text-muted tabular", gutterTone[line.kind])}
      id={n !== null && line.kind !== "del" ? lineAnchorId(path, n) : undefined}
    >
      <span className="sr-only">{lineAria(line)}</span>
      <span aria-hidden className="inline-flex items-center gap-1">
        {onLineClick && n !== null && line.kind !== "del" ? (
          <button
            type="button"
            onClick={() => onLineClick(path, n)}
            className={cx("rounded-sm p-px text-primary hover:bg-surface-2", isNote ? "opacity-100" : "opacity-40 hover:opacity-100 focus-visible:opacity-100")}
            aria-label={t("practice.note.addOnLine", { n })}
          >
            <Plus className="size-3" aria-hidden />
          </button>
        ) : null}
        <span className="inline-block min-w-[2.5ch]">{line.oldNo ?? ""}</span>
        <span className="inline-block min-w-[2.5ch]">{line.newNo ?? ""}</span>
      </span>
    </th>
  );
}

function Code({ line, wrap }: { line: DiffLine; wrap: boolean }) {
  const sign = line.kind === "add" ? "+" : line.kind === "del" ? "−" : line.kind === "hunk" ? "" : " ";
  return (
    <td className={cx("px-2 align-top", wrap ? "whitespace-pre-wrap break-all" : "whitespace-pre", rowTone[line.kind])}>
      <span aria-hidden className="mr-2 inline-block w-[1ch] text-muted">
        {sign}
      </span>
      {line.text || " "}
    </td>
  );
}

function SlotRow({ children, colSpan, label }: { children: ReactNode; colSpan: number; label: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="bg-surface px-2 py-2 font-sans text-base whitespace-normal">
        <aside aria-label={label} className="sticky left-2 max-w-[min(100%,60rem)]">
          {children}
        </aside>
      </td>
    </tr>
  );
}

interface FileBodyProps {
  file: DiffFile;
  lines: DiffLine[];
  slots: Slots;
  props: DiffViewProps;
}

function UnifiedRows({ file, lines, slots, props }: FileBodyProps) {
  const { wrap = false, renderFinding, onLineClick, renderNote, noteLines, flash } = props;
  return (
    <>
      {lines.map((l) => {
        const after: ReactNode[] = [];
        if (l.newNo !== null && l.kind !== "del") {
          for (const f of slots.byLine.get(l.newNo) ?? []) after.push(renderFinding ? <Fragment key={f.id}>{renderFinding(f)}</Fragment> : null);
          if (renderNote && noteLines?.has(`${file.filename}:${l.newNo}`)) after.push(<Fragment key="note">{renderNote(file.filename, l.newNo)}</Fragment>);
        }
        if (l.oldNo !== null && l.kind === "del") for (const f of slots.byOldLine.get(l.oldNo) ?? []) after.push(renderFinding ? <Fragment key={f.id}>{renderFinding(f)}</Fragment> : null);
        const flashing = flash && flash.path === file.filename && flash.line !== null && flash.line === l.newNo;
        return (
          <Fragment key={l.key}>
            <tr className={cx(flashing && "k-flash")}>
              {l.kind === "hunk" ? (
                <td colSpan={2} className={cx("px-2 py-0.5 whitespace-pre", rowTone.hunk)}>
                  {l.text}
                </td>
              ) : (
                <>
                  <Gutter line={l} path={file.filename} onLineClick={onLineClick} isNote={noteLines?.has(`${file.filename}:${l.newNo}`)} />
                  <Code line={l} wrap={wrap} />
                </>
              )}
            </tr>
            {after.length ? (
              <SlotRow colSpan={2} label={t("diff.slotLabel", { n: l.newNo ?? l.oldNo ?? "" })}>
                <div className="space-y-2">{after}</div>
              </SlotRow>
            ) : null}
          </Fragment>
        );
      })}
    </>
  );
}

function SplitRows({ file, lines, slots, props }: FileBodyProps) {
  const { wrap = false, renderFinding } = props;
  const rows = useMemo(() => toSplitRows(lines), [lines]);
  return (
    <>
      {rows.map((r) => {
        if (r.kind === "hunk")
          return (
            <tr key={r.key}>
              <td colSpan={4} className={cx("px-2 py-0.5 whitespace-pre", rowTone.hunk)}>
                {r.left?.text}
              </td>
            </tr>
          );
        const rightNo = r.right?.newNo ?? null;
        const found = rightNo !== null ? (slots.byLine.get(rightNo) ?? []) : [];
        return (
          <Fragment key={r.key}>
            <tr>
              {r.left ? <Gutter line={{ ...r.left, newNo: r.left.kind === "ctx" ? null : r.left.newNo }} path={file.filename} /> : <td className="bg-surface-2" />}
              {r.left ? <Code line={r.left} wrap={wrap} /> : <td className="bg-surface-2" />}
              {r.right ? <Gutter line={{ ...r.right, oldNo: null }} path={file.filename} /> : <td className="bg-surface-2" />}
              {r.right ? <Code line={r.right} wrap={wrap} /> : <td className="bg-surface-2" />}
            </tr>
            {found.length && renderFinding ? (
              <SlotRow colSpan={4} label={t("diff.slotLabel", { n: rightNo ?? "" })}>
                <div className="space-y-2">{found.map((f) => <Fragment key={f.id}>{renderFinding(f)}</Fragment>)}</div>
              </SlotRow>
            ) : null}
          </Fragment>
        );
      })}
    </>
  );
}

/** Rows for very long files: a fixed-height scroller, virtualised; inline cards render below the block. */
function VirtualRows({ file, lines, props }: Omit<FileBodyProps, "slots">) {
  const { wrap = false } = props;
  const parentRef = useRef<HTMLDivElement>(null);
  const v = useVirtualizer({ count: lines.length, getScrollElement: () => parentRef.current, estimateSize: () => 22, overscan: 30 });
  return (
    <div ref={parentRef} className="max-h-[70dvh] overflow-auto" role="table" aria-label={t("diff.fileTable", { file: file.filename })}>
      <div role="rowgroup" style={{ height: `${v.getTotalSize()}px`, position: "relative" }}>
        {v.getVirtualItems().map((item) => {
          const l = lines[item.index]!;
          return (
            <div
              key={l.key}
              role="row"
              data-index={item.index}
              ref={v.measureElement}
              className={cx("absolute left-0 flex w-full", rowTone[l.kind])}
              style={{ transform: `translateY(${item.start}px)` }}
            >
              <span role="rowheader" className={cx("sticky left-0 shrink-0 px-2 text-right text-muted tabular", gutterTone[l.kind])}>
                <span className="sr-only">{l.kind === "hunk" ? l.text : lineAria(l)}</span>
                <span aria-hidden>
                  <span className="inline-block min-w-[3ch]">{l.oldNo ?? ""}</span> <span className="inline-block min-w-[3ch]">{l.newNo ?? ""}</span>
                </span>
              </span>
              <span role="cell" className={cx("px-2", wrap ? "whitespace-pre-wrap break-all" : "whitespace-pre")}>
                {l.kind === "add" ? "+ " : l.kind === "del" ? "− " : "  "}
                {l.text}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const FileBlock = memo(function FileBlock({ file, props }: { file: DiffFile; props: DiffViewProps }) {
  const [open, setOpen] = useState(!props.collapsedByDefault);
  const [forceLoad, setForceLoad] = useState(false);
  const parsed = useMemo(() => parsePatch(file.patch, file.filename), [file.patch, file.filename]);
  const slots = useMemo(() => slotFindings(file.filename, props.findings, parsed.lines), [file.filename, props.findings, parsed.lines]);
  const needsLoad = !file.binary && (Boolean(file.too_large) || file.patch === null || file.patch === undefined || parsed.lines.length > LARGE_THRESHOLD);
  const showLarge = needsLoad && !forceLoad;
  const virtual = parsed.lines.length > VIRTUAL_THRESHOLD;
  const cols = props.split ? 4 : 2;
  return (
    <section className="rounded-md border border-border bg-surface" id={fileAnchorId(file.filename)} aria-label={file.filename}>
      <header className="sticky top-0 z-[2] flex items-center gap-2 rounded-t-md border-b border-border bg-surface-2 px-3 py-1.5">
        <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-sm">
          {open ? <ChevronDown className="size-4 shrink-0" aria-hidden /> : <ChevronRight className="size-4 shrink-0" aria-hidden />}
          <FileCode className="size-4 shrink-0 text-muted" aria-hidden />
          <span className="truncate font-mono text-sm" title={file.filename}>
            {file.filename}
          </span>
        </button>
        <span className="shrink-0 text-xs tabular">
          <span className="text-success-fg">{t("diff.additions", { n: parsed.additions })}</span>{" "}
          <span className="text-danger-fg">{t("diff.deletions", { n: parsed.deletions })}</span>
        </span>
      </header>
      {open ? (
        <>
          {slots.fileLevel.length && props.renderFinding ? (
            <div className="space-y-2 border-b border-border p-2">{slots.fileLevel.map((f) => <Fragment key={f.id}>{props.renderFinding!(f)}</Fragment>)}</div>
          ) : null}
          {file.binary ? (
            <p className="p-3 text-sm text-muted">{t("diff.binary")}</p>
          ) : showLarge ? (
            <div className="flex flex-wrap items-center gap-3 p-3 text-sm text-muted">
              {t("diff.large")}
              <Button
                size="sm"
                onClick={() => {
                  setForceLoad(true);
                  if (file.patch === null || file.patch === undefined || file.too_large) props.onLoadLarge?.(file.filename);
                }}
              >
                {t("diff.loadAnyway")}
              </Button>
            </div>
          ) : parsed.lines.length === 0 ? (
            <p className="p-3 text-sm text-muted">{t("diff.noChanges")}</p>
          ) : virtual ? (
            <div className="font-mono text-code">
              <VirtualRows file={file} lines={parsed.lines} props={props} />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse font-mono text-code leading-relaxed" aria-label={t("diff.fileTable", { file: file.filename })}>
                <colgroup>
                  {Array.from({ length: cols }, (_, i) => (
                    <col key={i} className={i % 2 === 0 ? "w-0" : undefined} />
                  ))}
                </colgroup>
                <tbody>
                  {props.split ? <SplitRows file={file} lines={parsed.lines} slots={slots} props={props} /> : <UnifiedRows file={file} lines={parsed.lines} slots={slots} props={props} />}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
});

/** Keeper's own diff renderer (parse-diff); inline slots for finding cards and practice notes. */
export function DiffView(props: DiffViewProps) {
  if (!props.files.length) return <p className="p-4 text-sm text-muted">{t("diff.empty")}</p>;
  return (
    <div className="space-y-3" data-mode={props.mode ?? "review"}>
      {props.files.map((f) => (
        <FileBlock key={f.filename} file={f} props={props} />
      ))}
    </div>
  );
}
