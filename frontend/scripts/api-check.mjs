// Regenerates the API types into a temporary file and fails if src/api/schema.d.ts is stale.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const dir = mkdtempSync(join(tmpdir(), "keeper-api-"));
const out = join(dir, "schema.d.ts");
try {
  execFileSync("npx", ["openapi-typescript", "src/api/openapi.json", "-o", out, "--empty-objects-unknown"], { stdio: "ignore" });
  const fresh = readFileSync(out, "utf8");
  const current = readFileSync("src/api/schema.d.ts", "utf8");
  if (fresh !== current) {
    console.error("src/api/schema.d.ts is stale. Run: npm run api:gen");
    process.exitCode = 1;
  } else {
    console.log("API types are up to date.");
  }
} finally {
  rmSync(dir, { recursive: true, force: true });
}
