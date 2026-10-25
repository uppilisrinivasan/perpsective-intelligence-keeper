# Data

Keeper's claims stand or fall on data. This section defines what data Keeper needs, the exact schema each real source produces, how the demo data is generated so that it has that schema, how it is validated against ground truth, how it is stored in git, and how it maps into the database.

## Principles

1. **Source schema, exactly.** Demo data has the same files, shapes and field names as what Keeper would receive from the real source (the GitHub REST API, git, pytest JUnit XML). One adapter reads both demo and real data. Generated JSON is validated against schemas extracted from GitHub's published OpenAPI description.
2. **AI generates values only.** Structure, identifiers, timestamps, counts, URLs, diffs, hunks, line numbers, SHAs and test results are produced by code or by actually running git and pytest. Models write code, prose and comments. The contract is in [Synthetic data generation](06-synthetic-data-generation.md) §1.
3. **Planted phenomena, separate truth.** The data deliberately contains every phenomenon Keeper must detect (edge concerns, blind spots, bias, drift, risky changes, slop, outcomes). The labels live only in `data/ground_truth/`, which the pipeline never reads.
4. **Reproducible and committed.** Generation is seeded, staged and content-addressed. Its outputs, the git bundle, the ground truth and the saved analysis snapshot are committed to git, so a clean clone runs the full demo with no API key.
5. **Real data is welcome.** The same pipeline imports public repositories through the GitHub API, with consent and attribution rules.

## Documents

| # | Document | Content |
|---|---|---|
| 01 | [Data inventory](01-data-inventory.md) | Every dataset, its purpose, source, real or synthetic, and volume |
| 02 | [Source schema: GitHub REST API](02-source-schema-github.md) | Endpoints, payload fields, the mirror layout, what Keeper uses |
| 03 | [Source schema: git, CI and repository files](03-source-schema-git-ci-files.md) | Git bundle, commit conventions, JUnit XML, check runs, CODEOWNERS and others |
| 04 | [External data](04-external-data.md) | Real-repository import, CodeReviewer, OSV, Tavily |
| 05 | [Synthetic world scenario](05-synthetic-world-scenario.md) | `config/datagen/scenario.yaml`: personas, the repository, concern slots, timeline, the live queue |
| 06 | [Synthetic data generation](06-synthetic-data-generation.md) | Stages G0–G12, who produces which value, validation loops, cost |
| 07 | [Ground truth and validation](07-ground-truth-and-validation.md) | Label files, validators, the evaluation harness |
| 08 | [The `data/` folder and git](08-data-folder-and-git.md) | Layout, size budget, manifest, what is committed and what is ignored |
| 09 | [Internal data model](09-internal-data-model.md) | Database tables and their relations |
