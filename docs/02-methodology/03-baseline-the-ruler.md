# The baseline, or ruler: C(S)

> "In Perspective Intelligence, the open model is the ruler, not the oracle." (IP, one-page summary)

## 1. What the baseline is

C(S) is what a **competent generic reviewer** notices in the PR: Nemotron reviewing with no knowledge of this project's maintainer, plus standard static tools. It represents "the view from everywhere" applied to this PR. It is deliberately a *good* reviewer, not a strawman. If the baseline is weak, the residual is inflated and Keeper's claims become meaningless.

## 2. Components

| Component | Config (`config/baseline.yaml`) | Notes |
|---|---|---|
| LLM reviewer | `llm.role: judge`, `llm.prompt: baseline_review`, `llm.temperature: 0`, `llm.top_p: 1`, `llm.seed: 7`, `llm.reasoning: low`, `llm.max_findings: 15` | The same model role as the lens review (Super) |
| ruff | `tools.ruff.enabled: true`, `tools.ruff.select: ["E", "F", "B", "UP", "SIM", "PERF"]`, `category_map: {F: correctness, B: correctness, PERF: performance, default: style}` | Run on changed files; keep only hits on added lines |
| bandit | `tools.bandit.enabled: true`, `tools.bandit.severity_min: low`, `category_map: {default: security}` | Python only; changed lines only |
| Tool versions | From the backend lockfile, recorded in the ruler | — |

The baseline prompt (`baseline_review`, see [Prompt catalog](15-prompt-catalog.md)) asks for a careful senior review of the PR context block in the shared finding schema. It covers correctness, tests, security, performance, API, docs and style. It forbids speculating about the project's history. Same context, same schema, same model as the lens review: the only thing the lens adds is the lens block.

## 3. The ruler record

```jsonc
{
  "id": "rul_3f9a…",                 // hash of the canonical JSON of the fields below
  "llm": {"model_id": "nvidia/nemotron-3-super-120b-a12b", "prompt_id": "baseline_review",
          "prompt_version": 3, "prompt_sha256": "…", "params": {"temperature": 0, "top_p": 1, "seed": 7, "reasoning": "low"}},
  "tools": {"ruff": "0.8.x (from lockfile)", "bandit": "1.8.x (from lockfile)", "ruff_select": ["E","F","B","UP","SIM","PERF"]},
  "context_config_sha256": "…",
  "taxonomy_sha256": "…",
  "created_at": "…"
}
```

Rules:
1. The ruler ID is the content hash, so any change to the model, prompt, parameters, tools, context bounds or taxonomy yields a new ruler automatically.
2. `residual_samples`, `lens_versions`, `fidelity_runs` and `growth_snapshots` reference `ruler_id`. The API rejects comparisons across rulers with `409 ruler_mismatch`.
3. The **active ruler** is the one built from the current config. If the active ruler differs from the ruler of the current lens version, the Lens screen shows "Generic review changed since this lens was built. Re-measure?" Re-measuring re-runs L3, L4 and L6.
4. **Model fallback and the ruler.** If the configured `judge` model is unavailable and the gateway falls back, baseline calls under that ruler fail instead of falling back (`allow_fallback: false` for `baseline_review`), because a different model is a different ruler. Analysis then shows "Generic review unavailable (model X offline)" and routing treats C as empty with a warning. *Rationale:* a silently moved ruler is exactly what the papers warn against.

## 4. Determinism and caching

- Temperature 0 and a fixed seed. Token Factory may not guarantee bit-identical outputs, so each baseline reading is **computed once and stored** (keyed by head SHA and ruler ID). That stored reading *is* C(S) for every later comparison.
- The stored reading includes the raw model output, for audit.

## 5. Static-tool findings

- Hits are converted to findings with `kind = tool`, `refs.tool = "ruff:F841"`, severity from a map (`error → minor`, `warning → nit`; bandit `HIGH → major`, `MEDIUM → minor`, `LOW → nit`), and an anchor at the hit line.
- Static findings are part of C for matching, so a maintainer's style nit that ruff also reports is `shared`.
- Tools run in the sandbox runner (they read untrusted code) with the same isolation as tests.

## 6. Baseline quality checks (shown in Proof → "How we measure")

| Check | Meaning | Target on the demo |
|---|---|---|
| Baseline recall of shared-ground slots | Does the baseline catch the things any good reviewer catches (planted style, tests and generic bug slots)? | ≥ 0.7 |
| Baseline noise per PR | Findings that match neither the human nor any outcome | Reported, no target |
| Baseline on blind-spot slots | Does it catch what the maintainer misses (planted)? | ≥ 0.6 (otherwise the blind-spot lane cannot work) |

If the baseline is too weak on shared-ground slots, the prompt is improved *before* any lens is built, and a new ruler is created. Prompt changes are never tuned on held-out PRs.
