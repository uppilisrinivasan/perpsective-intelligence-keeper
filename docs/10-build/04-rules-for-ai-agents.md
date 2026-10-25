# Rules for AI agents building Keeper

Read this first. These rules override convenience.

## 1. Source of truth

1. The **documents in `docs/`** are the specification. If code and docs disagree, the docs win, unless the docs are wrong. Then fix the docs in the same change and record it in `docs/build-log.md` (date, what changed, why).
2. Requirement IDs (`BR-`, `FR-`, `NFR-`) are cited in commit messages and in test docstrings.
3. When an external fact is marked **[verify]**, check it (docs, `--help`, or a probe) before relying on it, and implement a runtime check if it can change.

## 2. Never

1. **Never hardcode** demo values, model IDs, thresholds, ports, URLs or user-facing text in code. Read them from `data/`, `config/`, `.env` or `copy/en.json`. The hardcode guard ([Testing](03-testing-strategy.md) §6) fails the build.
2. **Never put a secret** anywhere except `.env` (locally). Do not print secrets, log them, put them in fixtures, or send them to the frontend or a sandbox. Do not commit `.env`.
3. **Never write to GitHub** or any external system on a user's behalf.
4. **Never let the lens lower attention** or let a risk-signal PR be `shared`.
5. **Never run model-supplied commands.** Only recipe commands run in sandboxes.
6. **Never silently change the ruler** (no fallback for `baseline_review`).
7. **Never invent data values in code** to make a screen look good. If data is missing, show the designed empty state.
8. **Never generate data that breaks the source schema.** AI generates values; code generates structure. Validate against the GitHub schemas.
9. **Never mix ground truth into the pipeline.** Only `keeper.eval` and `keeper.datagen` read `data/ground_truth/`.
10. **Never use fixed pixel layouts** or assume a screen resolution.
11. Never add a dependency without pinning it and noting why in the PR description; prefer the stack listed in [System architecture](../04-architecture/01-system-architecture.md) §2.

## 3. Always

1. Use the gateway for every model call, with a prompt file and an output schema.
2. Write the test first for the pure logic (routing, statistics, forms, health).
3. Keep functions in `keeper.route`, `keeper.residual`, `keeper.fidelity`, `keeper.growth` and `keeper.calibrate` pure (no I/O); pass data in.
4. Run `./run.sh --test` before declaring a task done; run `./run.sh --check` after touching config or env.
5. Use the generated OpenAPI types in the frontend; never hand-write API types.
6. Use the design tokens and the component catalog; add a component to the catalog document if you create a shared one.
7. Label every model-produced text for others with the Keeper label.
8. Keep the no-key mode working for every new screen or feature (snapshot data plus `KeyRequired` states).
9. Update the docs when behaviour changes.

## 4. How to pick up a task

1. Find the milestone in the [Implementation plan](02-implementation-plan.md) and read the documents it lists.
2. Check `docs/build-log.md` for decisions already made.
3. Implement, test, and update the [Definition of done](05-definition-of-done.md) checklist items for the milestone.
4. Note any deviation or open question in `docs/build-log.md`.
