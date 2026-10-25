/**
 * Token contrast (docs/06-frontend/07-accessibility.md): text tokens ≥ 4.5:1 on bg and surface, lane fg on lane bg
 * ≥ 4.5:1, lane solids and the focus ring ≥ 3:1 against the surface, in both themes. OKLCH → sRGB → WCAG luminance.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const css = readFileSync(resolve(__dirname, "../../src/styles/tokens.css"), "utf8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(selector);
  if (start < 0) throw new Error(`missing ${selector}`);
  const open = css.indexOf("{", start);
  let depth = 0;
  let end = open;
  for (let i = open; i < css.length; i++) {
    if (css[i] === "{") depth++;
    if (css[i] === "}" && --depth === 0) {
      end = i;
      break;
    }
  }
  const out: Record<string, string> = {};
  for (const m of css.slice(open + 1, end).matchAll(/--([\w-]+):\s*([^;]+);/g)) out[m[1]!] = m[2]!.trim();
  return out;
}

const light = block(":root {");
const dark = { ...light, ...block(':root[data-theme="dark"] {') };

export function oklchToRgb(l: number, c: number, hDeg: number): [number, number, number] {
  const h = (hDeg * Math.PI) / 180;
  const a = c * Math.cos(h);
  const b = c * Math.sin(h);
  const l_ = l + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = l - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = l - 0.0894841775 * a - 1.291485548 * b;
  const L = l_ ** 3;
  const M = m_ ** 3;
  const S = s_ ** 3;
  const lin = [4.0767416621 * L - 3.3077115913 * M + 0.2309699292 * S, -1.2684380046 * L + 2.6097574011 * M - 0.3413193965 * S, -0.0041960863 * L - 0.7034186147 * M + 1.707614701 * S];
  return lin.map((x) => Math.min(1, Math.max(0, x))) as [number, number, number];
}

function luminance(token: string): number {
  const m = /oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/.exec(token);
  if (!m) throw new Error(`not oklch: ${token}`);
  const [r, g, b] = oklchToRgb(Number(m[1]), Number(m[2]), Number(m[3]));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

const LANES = ["edge", "blind", "shared", "unknown", "baseline"];
const SEMANTIC = ["success", "warning", "danger", "info"];

describe.each([
  ["light", light],
  ["dark", dark],
])("%s theme contrast", (_name, theme) => {
  const v = (k: string) => {
    const x = theme[k];
    if (!x) throw new Error(`missing --${k}`);
    return x;
  };
  it.each(["text", "text-muted"])("--%s ≥ 4.5:1 on bg, surface and surface-2", (k) => {
    for (const bg of ["bg", "surface", "surface-2"]) expect(contrast(v(k), v(bg)), `${k} on ${bg}`).toBeGreaterThanOrEqual(4.5);
  });
  it.each(LANES)("lane %s: fg ≥ 4.5:1 on its bg and on surface; solid ≥ 3:1 on surface", (lane) => {
    expect(contrast(v(`lane-${lane}-fg`), v(`lane-${lane}-bg`))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(v(`lane-${lane}-fg`), v("surface"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(v(`lane-${lane}-solid`), v("surface"))).toBeGreaterThanOrEqual(3);
  });
  it.each(SEMANTIC)("%s: fg ≥ 4.5:1 on its bg", (s) => {
    expect(contrast(v(`${s}-fg`), v(`${s}-bg`))).toBeGreaterThanOrEqual(4.5);
  });
  it("focus ring ≥ 3:1 on bg and surface; primary button text ≥ 4.5:1", () => {
    expect(contrast(v("focus"), v("bg"))).toBeGreaterThanOrEqual(3);
    expect(contrast(v("focus"), v("surface"))).toBeGreaterThanOrEqual(3);
    expect(contrast(v("on-primary"), v("primary"))).toBeGreaterThanOrEqual(4.5);
  });
  it("the media-query dark block matches the explicit dark block", () => {
    const media = block(':root:not([data-theme="light"]) {');
    expect(media).toEqual(block(':root[data-theme="dark"] {'));
  });
});

describe("oklch conversion", () => {
  it("maps white and black", () => {
    expect(oklchToRgb(1, 0, 0).map((x) => Math.round(x * 100) / 100)).toEqual([1, 1, 1]);
    expect(oklchToRgb(0, 0, 0)).toEqual([0, 0, 0]);
  });
});
