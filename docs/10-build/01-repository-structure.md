# Repository structure

This is the structure the repository root (`projects/perpsective-intelligence-keeper/`) must have when built. The documentation is in `docs/` and already exists. Everything else is created by the build.

```
.
├── run.sh                         # the one command (08-run/01-run-sh.md)
├── .env.example                   # committed template (07-configuration/01-env-file.md)
├── .env                           # NOT committed: secrets
├── .gitignore                     # 07-configuration/02-gitignore-and-secrets.md
├── .gitattributes                 # data/ binary rules (03-data/08-data-folder-and-git.md)
├── .pre-commit-config.yaml
├── LICENSE                        # Apache-2.0
├── README.md                      # written last (09-deployment/04-hackathon-submission.md §1)
├── config/                        # non-secret configuration (07-configuration/03-config-files.md)
│   ├── models.yaml  pricing.yaml  taxonomy.yaml  context.yaml  baseline.yaml  matching.yaml
│   ├── lens.yaml  routing.yaml  review.yaml  fix.yaml  sandbox.yaml  find.yaml
│   ├── fidelity.yaml  growth.yaml  eval.yaml  datasets.yaml  redaction.yaml  glossary.yaml  ui.yaml
│   ├── sandbox/macos-deny-network.sb
│   ├── prompts/                   # *.md (front matter + Jinja), _voice.md, versions.lock
│   ├── schemas/
│   │   ├── config/                # JSON Schemas for each YAML above
│   │   ├── llm/                   # one output schema per prompt
│   │   ├── github/                # extracted from github/rest-api-description
│   │   └── lens_package.schema.json
│   └── datagen/                   # scenario.yaml, profiles/, denylist.txt, real_packages.yaml, slot_checks.yaml
├── data/                          # COMMITTED generated dataset (03-data/08-data-folder-and-git.md)
│   ├── README.md  manifest.json
│   ├── sources/{github/<owner>/<repo>/…, git/<repo>.bundle, ci/junit/<sha>.xml}
│   ├── ground_truth/…
│   ├── snapshots/<project>/…
│   └── generated/{validation_report.json, baseline_measurement.json, eval_report.json}
├── backend/
│   ├── pyproject.toml  uv.lock  requirements.lock  sandbox-requirements.txt  .importlinter  alembic.ini
│   ├── keeper/
│   │   ├── core/        types.py taxonomy.py timeutil.py textsim.py
│   │   ├── config/      __init__.py settings.py loader.py
│   │   ├── db/          models.py session.py repo.py migrations/
│   │   ├── llm/         gateway.py providers.py prompts.py schemas.py redact.py meter.py cache.py batch.py probe.py record.py
│   │   ├── jobs/        runner.py local.py nebius.py events.py remote.py
│   │   ├── sandbox/     base.py local.py docker.py contree.py recipes.py select.py
│   │   ├── sources/     github/{client,mirror,importer}.py git.py junit.py osv.py tavily.py repo_files.py
│   │   ├── ingest/      …
│   │   ├── findings/    extract.py anchors.py merge.py
│   │   ├── baseline/    ruler.py review.py tools.py
│   │   ├── residual/    match.py candidates.py
│   │   ├── lens/        build.py apply.py card.py diff.py package.py governance.py digest.py
│   │   ├── route/       lanes.py risk.py triage.py handoff.py attention.py
│   │   ├── review/      draft.py export.py
│   │   ├── fix/         runner.py edits.py
│   │   ├── outcomes/    link.py
│   │   ├── calibrate/   stats.py bias.py
│   │   ├── find/        edge_map.py
│   │   ├── fidelity/    run.py metrics.py bootstrap.py falsifiers.py
│   │   ├── growth/      practice.py residual.py health.py forms.py
│   │   ├── analysis/    context.py codeindex.py pipeline.py
│   │   ├── services/    queue.py pulls.py fixes.py lens.py proof.py practice.py projects.py settings.py usage.py tour.py
│   │   ├── assistant/   loop.py tools.py cards.py
│   │   ├── app/         __init__.py (create_app) __main__.py routers/ events.py auth.py errors.py static.py export_openapi.py
│   │   ├── cli/         __main__.py
│   │   ├── datagen/     __main__.py stages/ validate.py snapshot.py
│   │   └── eval/        truth.py harness.py report.py
│   └── tests/           unit/ integration/ api/ e2e_backend/ fixtures/{llm,github,repos}/ conftest.py
├── frontend/
│   ├── package.json  package-lock.json  vite.config.ts  tsconfig.json  eslint.config.js  playwright.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx  App.tsx  routes.tsx
│       ├── api/        client.ts sse.ts openapi.json schema.d.ts hooks/*.ts
│       ├── copy/       en.json  t.ts
│       ├── styles/     tokens.css  globals.css
│       ├── components/ ui/*  keeper/*
│       ├── screens/    queue/ pull/ ask/ lens/ proof/ practice/ settings/ signin/ dev/
│       ├── state/      role.ts  prefs.ts  tour.ts
│       └── lib/        format.ts  diff.ts  shortcuts.ts
│   └── tests/          unit/  e2e/  a11y/  visual/
├── infra/
│   ├── docker/         Dockerfile  entrypoint.sh  .dockerignore
│   └── nebius/         deploy.sh  smoke.sh  check_status.sh  README.md
├── scripts/            fetch_codereviewer.py  extract_github_schemas.py
├── .github/workflows/  ci.yml
└── docs/               (this documentation)
```

Notes:
- `.dockerignore` lives at the repository root for the build context (it is shown under `infra/docker/` for grouping; copy or symlink it to the root).
- The `docs/assets/` folder holds the screenshots referenced by the README (taken from the running app, never mock-ups).
