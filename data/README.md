# Demo data (fictional)

This folder is the complete demo world for Keeper: a fictional open-source project, `fernhill-oss/lamina`,
with three years of history in exactly the shape of the GitHub REST API (v2022-11-28), its real git repository
(as a bundle) and real pytest results. Nobody in it is a real person; all hosts are `*.github.example`.

- `sources/`: what the real sources produce: the GitHub mirror, `git/lamina.bundle`, CI JUnit XML, and
  `keeper/practice_notes.json` (the demo learner's notes, as Keeper's own UI would store them).
- `ground_truth/`: what was planted, for evaluation only. Keeper's pipeline never reads it.
- `snapshots/`: Keeper's saved analysis of this project, used when no model API key is configured.
- `generated/`: validation and evaluation reports.

How it was made: `python -m keeper.datagen run` (seed 20261025, profile `demo`). The values (code, PR text,
review wording) are authored in `config/datagen/world.yaml` and the code templates; code produced every structural
field; git and pytest produced diffs, SHAs and test results. Released under the repository's licence (Apache-2.0).
