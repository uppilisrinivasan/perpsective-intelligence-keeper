# Screen: Settings

**Question answered:** "Is Keeper set up correctly, and what has it cost?" **Requirements:** FR-SET. Tabs (`?tab=`): **Models**, **Usage**, **Sandbox**, **Projects**, **Preferences**, **About**.

## 1. Models

| Row | Content |
|---|---|
| Provider | "Nebius Token Factory · key configured ✓" or "No key: Keeper is showing saved results" + a how-to (the `.env` line `NEBIUS_API_KEY=` and a restart, or `./run.sh --check`) |
| Each role | The role in plain words ("Fast: reading history and quick checks", "Judge: reviews and matching", "Deep: building the lens and writing fixes", "Assistant"), the display name and model ID, and the probe results as chips (Available, JSON schema ✓, Reasoning control ✓, Tools ✓); a fallback notice if active |
| Actions | **Check again** (re-run the probe) |

Keys are never shown, typed or stored in the UI. Changing models is done in `.env` (explained inline).

## 2. Usage

- A period switch (Today, This month, All time).
- `SpendMeter`: used against the cap, with when it resets.
- A table by feature (Queue, PR, Fix, Lens, Proof, Practice, Ask, plus Data generation if any): calls, tokens and cost. Another by model. A per-day bar list.
- The editable **auto-approve below** value (`KEEPER_AUTO_APPROVE_USD`; the UI override is bounded by `ui.yaml` `editable_settings`; the cap itself is env-only).

## 3. Sandbox

The provider in use, why ("Token Factory Sandboxes: not enabled for this project, using Docker"), the isolation level in plain words, the test recipe, and **Run a sandbox check** (runs the demo repository's tests once).

## 4. Projects

The list of projects with counts and the active badge; **Import a public repository** (a form: URL, maintainer login (an autocomplete after a lookup), time window, maximum PRs, with the estimated API calls, duration and model cost, and the notes on attribution and consent); **Delete project data** for imported projects.

## 5. Preferences

From `config/ui.yaml` `editable_settings`: the weekly attention budget (minutes), theme, density (comfortable or compact), diff wrap, default diff view, reduced motion (follow the system, or force), and show baseline-only notes by default. Each has **Reset**.

## 6. About

Version, data manifest (generated at, seed, hashes, "synthetic world" note), licences and attributions, and links to the docs and the source.
