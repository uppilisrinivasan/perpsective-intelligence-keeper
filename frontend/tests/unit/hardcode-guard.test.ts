/**
 * Hardcode guard (docs/10-build/03-testing-strategy.md §6) for frontend/src.
 * 1. Demo values from data/manifest.json (owner, repo, logins, display names) must not appear as whole words.
 * 2. Model IDs and names: the provider prefix and the model family name never appear in src.
 * 3. Ports from .env.example never appear in src.
 * Generated API files (openapi.json, schema.d.ts) are excluded: they are the backend's contract.
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const FRONTEND = resolve(__dirname, "../..");
const SRC = join(FRONTEND, "src");
const MANIFEST = resolve(FRONTEND, "../data/manifest.json");
const EXCLUDE = new Set(["api/openapi.json", "api/schema.d.ts"]);

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return walk(p);
    return /\.(tsx?|json|css|html)$/.test(name) ? [p] : [];
  });
}

const files = walk(SRC).filter((p) => !EXCLUDE.has(relative(SRC, p).split("\\").join("/")));
const sources = files.map((p) => ({ path: relative(FRONTEND, p), text: readFileSync(p, "utf8") }));

function escape(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Collects identifiers from the manifest: project owner/repo and any login or display-name values. */
export function demoValues(manifest: unknown): string[] {
  const out = new Set<string>();
  const visit = (v: unknown, key = "") => {
    if (typeof v === "string") {
      if (/(^|_)(owner|repo|login|logins|display_name|name|names)$/.test(key) && v.length >= 3 && !v.includes("/") && !v.includes(" ") ) out.add(v);
      if (/(display_name|names?)$/.test(key) && v.includes(" ")) v.split(" ").filter((w) => w.length >= 3).forEach((w) => out.add(w));
      return;
    }
    if (Array.isArray(v)) v.forEach((x) => visit(x, key));
    else if (v && typeof v === "object") for (const [k, x] of Object.entries(v)) if (k !== "files" && k !== "models_used") visit(x, k);
  };
  visit(manifest);
  return [...out];
}

describe("hardcode guard", () => {
  it.skipIf(!existsSync(MANIFEST))("has no demo names, owners or repositories in src", () => {
    const values = demoValues(JSON.parse(readFileSync(MANIFEST, "utf8")));
    const hits: string[] = [];
    for (const v of values) {
      const re = new RegExp(`(?<![\\w-])${escape(v)}(?![\\w-])`, "i");
      for (const s of sources) if (re.test(s.text)) hits.push(`${v} in ${s.path}`);
    }
    expect(hits).toEqual([]);
  });

  it("has no model IDs or model names in src", () => {
    const banned = ["nvidia" + "/", "Nemo" + "tron"];
    const hits = sources.flatMap((s) => banned.filter((b) => s.text.toLowerCase().includes(b.toLowerCase())).map((b) => `${b} in ${s.path}`));
    expect(hits).toEqual([]);
  });

  it("has no hardcoded ports in src", () => {
    const envExample = resolve(FRONTEND, "../.env.example");
    const ports = existsSync(envExample)
      ? [...readFileSync(envExample, "utf8").matchAll(/^(?:APP_PORT|FRONTEND_DEV_PORT)\s*=\s*(\d+)/gm)].map((m) => m[1]!)
      : [];
    const hits = sources.flatMap((s) => ports.filter((p) => new RegExp(`(?<!\\d)${p}(?!\\d)`).test(s.text)).map((p) => `${p} in ${s.path}`));
    expect(hits).toEqual([]);
  });

  it("extracts demo values from a manifest shape", () => {
    const sample = { project: { owner: "org-x", repo: "repo-y", primary_maintainer_login: "login-z", fictional: true }, files: { "sources/a.json": "sha" } };
    expect(demoValues(sample).sort()).toEqual(["login-z", "org-x", "repo-y"]);
  });
});
