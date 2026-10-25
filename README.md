# Keeper: a maintainer's eye that scales

> Keeper learns what one open-source maintainer notices in code review that generic AI misses, uses it to
> triage their pull-request queue, writes and tests the fixes they'd ask for, and checks itself on PRs it never saw.
> Built for NVIDIA Nemotron via Nebius Token Factory.

Apache-2.0 · Documentation: [docs/](docs/README.md) · Build notes and deviations: [docs/build-log.md](docs/build-log.md)

## Quick start

    git clone <repo> && cd <repo> && ./run.sh

This opens http://127.0.0.1:8430. Without a key, you see the saved results committed in `data/snapshots/`.
**The committed snapshot is an offline simulation** (`LLM_PROVIDER=fake`), not a Nemotron run, and the app labels it
"Saved results · offline simulation" everywhere. To run live, put `NEBIUS_API_KEY=<your key>` in `.env` (created by
`./run.sh`) and restart. To replace the snapshot with a real one, run `./run.sh --snapshot`, which asks before spending.

Requirements: Python 3.11+, Node 20.19+, git ≥ 2.34. Docker is optional; without it, fixes run in the local sandbox.

| Command | What it does |
|---|---|
| `./run.sh` | Install if needed, build if needed, start (one process) |
| `./run.sh --dev` | Backend auto-reload plus the Vite dev server |
| `./run.sh --check` | Diagnostics: `.env`, config schemas, prompt lock, data manifest, model probe, sandbox, secrets, port |
| `./run.sh --test` | Backend tests (offline), ruff, frontend tests, type check and lint |
| `./run.sh --eval` | Evaluation against the ground truth → `data/generated/eval_report.json` |
| `./run.sh --snapshot` | Rebuild `data/snapshots/` (with a key: live models, after confirmation; with `LLM_PROVIDER=fake`: offline) |
| `./run.sh --reset` | Delete `.runtime/` (database, caches, sandboxes); keeps `data/` and `.env` |

## What it does

- **Find:** reads a maintainer's past reviews and runs a pinned generic reviewer (the *ruler*) on the same PRs. The
  difference is what the maintainer notices that generic review misses (R+), and what generic review catches that the
  maintainer tends to miss and that later caused bugs (R−).
- **Build:** turns that residual into a *lens*: items with triggers, evidence, outcome calibration, a bias check and
  an owner-controlled card. Versions, diffs, export/import and revoke are built in.
- **Triage:** sorts the open queue into four lanes: *Needs your eye*, *Worth a second look*, *Needs another reviewer*
  and *Handled for you*. Risk signals only ever raise attention. Keeper drafts reviews and hand-off notes, but never
  posts, merges or writes to GitHub.
- **Fix and test:** plans a fix, applies it in a sandbox, runs the project's tests, repairs on failure and shows the
  diff as a downloadable patch. The sandbox runs only recipe commands, with no network.
- **Proof and Practice:** the Fidelity Test compares Keeper against generic review on held-out PRs with bootstrap
  intervals and falsifiers. The Growth Test lets a contributor practise noticing like the maintainer, measured before
  and after.
- **Ask:** a chat assistant that answers from Keeper's data through tools, cites what it uses, and proposes actions
  as confirmation cards.

## Models

| Task | Role (`config/models.yaml`) |
|---|---|
| Reading review history, lens recall, triage signals, fix verification | fast (Nemotron 3.5 Lightning) |
| Generic review (the pinned ruler; never falls back), lens review, matching, drafts, hand-offs, Ask | judge (Nemotron 3 Super) |
| Building the lens, planning and repairing fixes, calibration notes | deep (Nemotron 3 Ultra) |

Model IDs live only in `config/models.yaml` and `.env`. `./run.sh --check` probes them when a key is set.

## Results so far (offline simulation, not Nemotron)

These numbers come from the committed snapshot. That run used the deterministic offline simulator, so it shows the
pipeline working end to end; it says nothing about Nemotron's quality.

- **Fidelity Test (lens v1, 26 held-out PRs): not passed.** Keeper recovered 31% of what the maintainer raised;
  generic review recovered 31%. The difference is −1% (90% interval −18% to +16%). Keeper had less noise (0.73 vs
  2.35 notes per PR). The no-exaggeration criterion failed on category spread.
- **Eval harness** (`./run.sh --eval`): 6 checks pass, 4 fail and 2 are not measured. Pass: extraction precision 1.0,
  unknown-lane recall 1.0, both baseline slot recalls, edge map (3 of the top 4 planted) and fix success 1.0. Fail:
  extraction recall 0.73, routing macro-F1 0.58, lens edge-slot coverage 5 of 7, lens blind-spot items 0 of 2. Not
  measured: matching kappa (needs human labels) and held-out routing F1.
- **Fix and test:** the demo fix (#330 in the demo world) passed in the local sandbox.
- **Growth Test:** the demo learner's recall went from 0.16 before to 0.49 after. Those notes were authored with the
  world, so this only demonstrates the measurement.

## Data

`data/` holds a synthetic demo world, a fictional project with fictional people. It uses the exact GitHub REST
schemas (validated against GitHub's OpenAPI description), a real git history and real pytest results. The ground
truth is kept separate in `data/ground_truth/` and read only by `keeper.eval` and `keeper.datagen`. See
[docs/03-data/](docs/03-data/README.md).

## Known limitations

- The committed snapshot is simulated. A live snapshot and a live eval have not been run yet (they need a key and
  spend tokens).
- The data is synthetic and the held-out set is small (26 PRs), so the intervals are wide.
- Matching is judged by a model. Kappa against human labels is not measured.
- The local sandbox gives best-effort isolation (temp copy, separate venv, allow-listed env, no network on macOS
  via `sandbox-exec`). Docker gives more.
- Importing a real GitHub repository is not implemented yet. The job fails with a clear message.

## Configuration and secrets

`.env` is never committed. `.env.example` documents every setting. See [docs/07-configuration/](docs/07-configuration/01-env-file.md).

## Licence

Apache-2.0
