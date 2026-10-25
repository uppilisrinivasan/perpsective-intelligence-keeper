/**
 * Resolution guard (docs/10-build/03-testing-strategy.md §6.6): CSS must not set fixed layout widths or heights
 * in px. 1px/2px borders, outlines and rings are allowed. The ESLint rule keeper/no-fixed-px covers class strings.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const SRC = resolve(__dirname, "../../src");
const walk = (d: string): string[] => readdirSync(d).flatMap((n) => (statSync(join(d, n)).isDirectory() ? walk(join(d, n)) : n.endsWith(".css") ? [join(d, n)] : []));

describe("no fixed px layout", () => {
  it("has no px widths, heights or positions above 2px in CSS", () => {
    const hits: string[] = [];
    for (const f of walk(SRC)) {
      const text = readFileSync(f, "utf8");
      for (const m of text.matchAll(/(?:^|[;{\s])((?:min-|max-)?(?:width|height|inline-size|block-size)|top|left|right|bottom|inset)\s*:\s*([^;]+);/g)) {
        for (const px of m[2]!.matchAll(/(\d+(?:\.\d+)?)px/g)) if (Number(px[1]) > 2) hits.push(`${relative(SRC, f)}: ${m[1]}: ${m[2]}`);
      }
    }
    expect(hits).toEqual([]);
  });
});
