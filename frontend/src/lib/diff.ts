import parseDiff from "parse-diff";

/**
 * DiffFile.patch is a GitHub-style per-file unified patch that starts at "@@" (no ---/+++ header).
 * parse-diff needs a header, so one is prefixed. Finding anchors use new-side (RIGHT) line numbers.
 */
export type LineKind = "add" | "del" | "ctx" | "hunk";

export interface DiffLine {
  kind: LineKind;
  oldNo: number | null;
  newNo: number | null;
  text: string;
  key: string;
}

export interface ParsedPatch {
  lines: DiffLine[];
  additions: number;
  deletions: number;
}

export function parsePatch(patch: string | null | undefined, filename = "file"): ParsedPatch {
  if (!patch) return { lines: [], additions: 0, deletions: 0 };
  const body = patch.startsWith("diff --git") || patch.startsWith("--- ") ? patch : `--- a/${filename}\n+++ b/${filename}\n${patch}`;
  const files = parseDiff(body);
  const lines: DiffLine[] = [];
  let additions = 0;
  let deletions = 0;
  for (const f of files) {
    for (const chunk of f.chunks) {
      lines.push({ kind: "hunk", oldNo: null, newNo: null, text: chunk.content, key: `h${lines.length}` });
      for (const c of chunk.changes) {
        const raw = c.content;
        if (raw.startsWith("\\")) continue; // "\ No newline at end of file"
        const text = raw.length > 0 ? raw.slice(1) : "";
        if (c.type === "add") {
          additions++;
          lines.push({ kind: "add", oldNo: null, newNo: c.ln, text, key: `a${c.ln}-${lines.length}` });
        } else if (c.type === "del") {
          deletions++;
          lines.push({ kind: "del", oldNo: c.ln, newNo: null, text, key: `d${c.ln}-${lines.length}` });
        } else {
          lines.push({ kind: "ctx", oldNo: c.ln1, newNo: c.ln2, text, key: `c${c.ln2}-${lines.length}` });
        }
      }
    }
  }
  return { lines, additions, deletions };
}

export interface SplitRow {
  kind: "pair" | "hunk";
  left: DiffLine | null;
  right: DiffLine | null;
  key: string;
}

/** Pairs deletions with following additions for the side-by-side view. */
export function toSplitRows(lines: DiffLine[]): SplitRow[] {
  const rows: SplitRow[] = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i]!;
    if (l.kind === "hunk") {
      rows.push({ kind: "hunk", left: l, right: l, key: l.key });
      i++;
    } else if (l.kind === "ctx") {
      rows.push({ kind: "pair", left: l, right: l, key: l.key });
      i++;
    } else {
      const dels: DiffLine[] = [];
      const adds: DiffLine[] = [];
      while (i < lines.length && lines[i]!.kind === "del") dels.push(lines[i++]!);
      while (i < lines.length && lines[i]!.kind === "add") adds.push(lines[i++]!);
      const n = Math.max(dels.length, adds.length);
      for (let k = 0; k < n; k++) rows.push({ kind: "pair", left: dels[k] ?? null, right: adds[k] ?? null, key: `${dels[k]?.key ?? ""}|${adds[k]?.key ?? ""}` });
    }
  }
  return rows;
}

/** A single-hunk change formatted as a GitHub ```suggestion block (new side only). */
export function toSuggestion(patch: string | null | undefined): string | null {
  const parsed = parsePatch(patch);
  const hunks = parsed.lines.filter((l) => l.kind === "hunk").length;
  if (hunks !== 1) return null;
  const replacement = parsed.lines.filter((l) => l.kind === "add" || l.kind === "ctx").map((l) => l.text);
  return ["```suggestion", ...replacement, "```"].join("\n");
}

/** Splits a multi-file unified diff (git format) into per-file patches. */
export function splitMultiFileDiff(diff: string | null | undefined): Array<{ filename: string; patch: string }> {
  if (!diff) return [];
  const files = parseDiff(diff);
  return files.map((f) => {
    const filename = (f.to && f.to !== "/dev/null" ? f.to : f.from) ?? "file";
    const patch = f.chunks
      .map((c) => [c.content, ...c.changes.map((ch) => ch.content)].join("\n"))
      .join("\n");
    return { filename, patch };
  });
}
