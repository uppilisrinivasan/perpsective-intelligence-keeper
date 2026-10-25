import { num, obj, str, type Obj } from "./unknown";

/** Where "Open" goes for a finished job (toasts and Recent activity). */
export function jobHref(kind: string | undefined, params: Obj, result?: Obj): string | undefined {
  const p = obj(params);
  const r = obj(result);
  const n = num(p.number) ?? num(p.pr_number) ?? num(r.pr_number);
  switch (kind) {
    case "fix": {
      const fixId = str(r.fix_id) ?? str(r.id) ?? str(p.fix_id);
      return n && fixId ? `/pr/${n}/fix/${fixId}` : n ? `/pr/${n}` : undefined;
    }
    case "analyze":
    case "handoff":
      return n ? `/pr/${n}` : "/queue";
    case "triage":
      return "/queue";
    case "learn":
    case "lens_update":
    case "recalibrate":
      return "/lens?tab=versions";
    case "fidelity": {
      const run = str(r.run_id) ?? str(r.id);
      return run ? `/proof?run=${run}` : "/proof";
    }
    case "practice_score":
      return "/practice";
    case "import":
    case "probe":
    case "sandbox_check":
      return "/settings";
    default:
      return undefined;
  }
}
