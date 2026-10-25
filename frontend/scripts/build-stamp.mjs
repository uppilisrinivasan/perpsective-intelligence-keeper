// Writes dist/.build-stamp so run.sh can tell whether the built frontend is current.
import { writeFileSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";

const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const spec = readFileSync(new URL("../src/api/openapi.json", import.meta.url));
const stamp = {
  built_at: new Date().toISOString(),
  version: pkg.version,
  openapi_sha256: createHash("sha256").update(spec).digest("hex"),
};
writeFileSync(new URL("../dist/.build-stamp", import.meta.url), JSON.stringify(stamp, null, 2) + "\n");
