# Screens: first run, empty, loading and error states

## 1. First run

1. `./run.sh` opens the browser (if `OPEN_BROWSER=true`) at `/`.
2. If the `load_demo` job is still running: a centred card "Setting up the demo world" with steps (Checking data · Loading the repository · Loading saved results) and progress. It is typically under 30 s.
3. The welcome card for the tour ([App shell](../04-app-shell-and-tour.md) §3).
4. No key: the banner "You're seeing saved results from a real run on {date}. Add a Nemotron API key to run Keeper live." with **How** (a popover with the 3 steps) and **Dismiss**.

## 2. Pattern for every state

| State | Pattern | Example |
|---|---|---|
| Loading | Skeletons matching the final layout, shown after 150 ms (to avoid flashes); content streams in | Queue row skeletons |
| Long work | Inline `JobProgress`: the current step label, progress, elapsed time, cost so far, **Cancel**; a toast when done if the user left | "Building Mira's lens · Step 4 of 9: Grouping what Mira noticed" |
| Empty | `EmptyState`: icon composition, one sentence why, one primary next step | "No pull requests in this lane." + "Show all" |
| Not available without a key | `KeyRequired`: what it would do, what you can see instead | "Running a fix needs a Nemotron API key. See the saved fix run for #418." |
| Error (recoverable) | `InlineError`: what happened in plain words, **Try again**, a "Details" disclosure with the code and request ID | "The model took too long to answer. Try again." |
| Error (page) | `PageError`: the same pattern, plus **Go to Queue** | |
| Confirmation | `ConfirmCostDialog`: what will happen, the estimate, the remaining budget, "Don't ask again below $x" (sets auto-approve, bounded) | "Fix and test 1 finding · about $0.06 · up to 3 minutes" |
| Spend cap reached | A blocking banner across the app, actions disabled with a tooltip; all reading still works | "Keeper reached its $20 spending limit for this month. Saved and existing results still work." |
| Offline / server gone | A toast "Can't reach Keeper's server" with retry; the data on screen stays | |

## 3. Error copy map (API code → message)

| Code | Message | Action |
|---|---|---|
| `no_api_key` | "This needs a Nemotron API key." | How |
| `model_unavailable` | "{model} isn't available right now. Keeper tried {fallback} too." | Try again |
| `model_output_invalid` | "The model's answer didn't pass Keeper's checks." | Try again |
| `sandbox_unavailable` | "Keeper can't run tests here: {reason}." | Open Settings → Sandbox |
| `rate_limited` | "Too many requests. Trying again in {n} s." | Automatic |
| `spend_cap_reached` | See above | — |
| `consent_required` | "Keeper needs consent before building a lens for {name}." | Record consent |
| `job_in_progress` | "This is already running." | Show it |
| anything else | "Something went wrong." | Try again, Details |

The strings live in `frontend/src/copy/en.json` under `errors.*`.
