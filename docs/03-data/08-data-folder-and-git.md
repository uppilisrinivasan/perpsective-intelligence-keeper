# The `data/` folder and git

**The generated demo data is committed to git.** A clean clone must run the complete demo, including the saved analyses, without generating anything and without an API key.

## 1. Layout

```
data/
├── README.md                          # what this is, the fictional notice, how it was generated, the licence
├── manifest.json                      # versions, seed, profile, demo_now, counts, sha256 of every file
├── sources/                           # exactly what the real sources produce
│   ├── github/<owner>/<repo>/         # GitHub REST mirror (see 02-source-schema-github.md)
│   │   ├── _mirror.json
│   │   ├── repo.json
│   │   ├── labels.page-001.json
│   │   ├── pulls/index.page-001.json … page-003.json
│   │   ├── pulls/<n>/{pull.json, files.page-001.json, reviews.page-001.json, comments.page-001.json, commits.page-001.json}
│   │   ├── issues/index.page-001.json …
│   │   ├── issues/<n>/{comments.page-001.json, timeline.page-001.json}
│   │   └── commits/<sha>/check-runs.json
│   ├── git/<repo>.bundle              # the full repository with refs/heads/main and refs/pull/*/head
│   └── ci/junit/<sha>.xml             # pytest JUnit XML per PR head
├── ground_truth/                      # evaluation only; never read by the pipeline
│   └── … (see 07-ground-truth-and-validation.md)
├── snapshots/<project>/               # Keeper's own saved analysis of the demo (for no-key mode)
│   ├── snapshot.json                  # format version, ruler IDs, lens versions, the Keeper version, created_at, models used
│   ├── findings.jsonl                 # human, baseline and lens findings
│   ├── matches.jsonl
│   ├── residual_samples.jsonl
│   ├── lenses/<person>/v<k>/{lens_version.json, items.jsonl, LENS.md, digest.txt}
│   ├── outcomes.jsonl
│   ├── routes.jsonl                   # lanes, signals and reasons per PR (live queue and held-out)
│   ├── triage.jsonl
│   ├── review_drafts.jsonl
│   ├── fix_runs/<fix_id>/{fix_run.json, events.jsonl, final.patch, junit.xml}
│   ├── handoffs.jsonl
│   ├── edge_map.json
│   ├── fidelity_runs/<run_id>/{run.json, cases.jsonl}
│   ├── growth.json
│   ├── practice/{sessions.jsonl, answers.jsonl, results.jsonl}
│   ├── chat_examples.jsonl            # saved example Q&A for no-key Ask
│   └── llm_calls.jsonl                # audit of the calls that produced the snapshot (no prompts, only metadata)
└── generated/
    ├── validation_report.json
    ├── baseline_measurement.json      # V9b, if run
    └── eval_report.json
```

Datagen's intermediate work (`.runtime/datagen/`) is **not** committed: it is large and fully reproducible from the scenario, the seed and the cached model outputs. The **plan** (`plan.json`) is committed inside `ground_truth/`, because it is part of the truth.

## 2. Size budget

| Part | Budget (full profile) |
|---|---|
| `sources/github` | ≤ 18 MB (JSON is about 70% URL boilerplate, as in the real API) |
| `sources/git` bundle | ≤ 4 MB |
| `sources/ci` | ≤ 3 MB |
| `ground_truth` | ≤ 2 MB |
| `snapshots` | ≤ 8 MB |
| **Total** | **≤ 35 MB** (V8 enforces it) |

No Git LFS: judges clone with plain git. JSON files are written with sorted keys and 2-space indentation, so diffs between regenerations are reviewable.

## 3. `.gitattributes`

```
data/sources/git/*.bundle    binary
data/**/*.json               text eol=lf linguist-generated=true
data/**/*.jsonl              text eol=lf linguist-generated=true
data/sources/ci/junit/*.xml  text eol=lf linguist-generated=true
```

`linguist-generated` keeps GitHub's language statistics and PR diffs clean.

## 4. The manifest

```json
{
  "format_version": 1,
  "keeper_version": "0.1.0",
  "scenario": {"path": "config/datagen/scenario.yaml", "sha256": "…", "seed": 20261025, "profile": "full"},
  "demo_now": "2026-10-19T08:00:00Z",
  "project": {"id": "prj_demo", "owner": "acme-oss", "repo": "strata", "fictional": true,
              "primary_maintainer_login": "mira-k", "learner_login": "sam-r"},
  "splits": {"cutoff_v1": "2026-04-19T08:00:00Z", "holdout_end": "2026-10-19T08:00:00Z"},
  "models_used": {"datagen": {"deep": "nvidia/Nemotron-3-Ultra-550b-a55b", "judge": "nvidia/nemotron-3-super-120b-a12b", "fast": "nvidia/Nemotron-3_5-Lightning"}},
  "counts": {"pulls": 272, "reviews": 512, "review_comments": 1450, "issues": 130},
  "files": {"sources/github/acme-oss/strata/repo.json": "sha256:…", "…": "…"}
}
```

The manifest is the **only** place where demo names appear in non-generated form. Code reads them from here; it never contains them (hardcode guard, [Testing strategy](../10-build/03-testing-strategy.md) §6).

## 5. Committing regenerated data

1. `./run.sh --generate-data` (or the datagen commands), then `python -m keeper.datagen validate --deep`.
2. `./run.sh --eval` must pass.
3. `git add data/ config/datagen/ && git commit -m "data: regenerate demo (seed …, profile full)"`.
4. Record the regeneration in `docs/build-log.md` (date, models, cost, the eval summary).

## 6. What never goes into git

`.runtime/` (database, unpacked repositories, imported mirrors, caches, logs, the datagen ledger), `.env`, any imported project's data, and downloaded datasets. See [`.gitignore` and secrets](../07-configuration/02-gitignore-and-secrets.md).
