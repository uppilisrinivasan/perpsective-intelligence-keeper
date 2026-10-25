# Personas and user journeys

Names below are example values for the demo world. The real names are generated (see [Synthetic world scenario](../03-data/05-synthetic-world-scenario.md)) and read from data.

## 1. Personas

### P1 · The maintainer (primary)

*Example: Mira, sole long-standing maintainer of `strata`, a dependency-free Python library for layered configuration files that is used by thousands of projects.*

| Aspect | Detail |
|---|---|
| Situation | Unpaid; about 2 hours a week for review. Thousands of review comments over 3 years. |
| Pains | A flood of AI-generated PRs; generic AI review noise; fear of missing the one dangerous change; nobody to hand the project to. |
| What they notice that others miss | Invariants (round-trip fidelity, no new runtime dependencies), history ("we tried caching here in #212; it raced"), the threat model (include paths, environment interpolation), the hot path in the tokenizer, error messages that carry line and column. |
| Blind spots | Windows path and encoding edge cases; file handles left open on error paths. |
| Possible bias | Asks first-time contributors for extra tests more often than others, for comparable changes. |
| Wants from Keeper | "Do the routine work, show me only what needs me, tell me what I tend to miss, and never speak for me." |
| Success | The queue is cleared in under an hour; nothing risky is merged unseen; a contributor becomes trusted. |

### P2 · The contributor and would-be successor (secondary)

*Example: Sam, has sent small, good patches for months and wants to become a co-maintainer.*

| Aspect | Detail |
|---|---|
| Pains | Does not know the project's unwritten rules; reviews feel arbitrary; AI tools teach the average. |
| Wants | To learn what the maintainer looks for, practise on real PRs, and see progress. |
| Success | Unassisted review checks catch more of what the maintainer caught; the maintainer trusts them with a module. |

### P3 · The another-lens reviewer (tertiary)

*Example: Theo, a security-minded contributor who reviews build, release and parsing changes.*

| Aspect | Detail |
|---|---|
| Wants | Only the PRs that need a security eye, with the specific signals and context. |
| In Keeper | Appears as the hand-off target. Has their own lens, learned from their reviews. |

### P4 · The hackathon judge (the first real user)

| Aspect | Detail |
|---|---|
| Situation | Has 2–5 minutes, has watched the video, and is opening the URL cold. Expert in Nemotron and Token Factory; may not be an open-source maintainer. |
| Wants | To see the claim work, see which model does what, and trust that it is real and not scripted. |
| Success | Understands the four lanes without reading; sees the aha; sees live model calls; sees honest limits. |

## 2. Journeys

Each journey lists the steps, the screen, and the requirement IDs it exercises.

### J1 · First visit: the judge's two minutes

| # | Step | Screen | FR |
|---|---|---|---|
| 1 | Opens the URL and enters the access code (cloud only). | Sign-in | FR-SET-6 |
| 2 | Sees Queue with a welcome card: "Keeper has learned how Mira reviews. Take the 2-minute tour, or explore." The tour starts. | Queue + tour | FR-TOUR-1 |
| 3 | Tour step 1, *The aha*: opens a held-out PR in *Compare* view with three columns: Generic review, What Mira wrote, Keeper. The subtle finding is highlighted in all the places it appears, with the citation of an earlier PR. | PR view | FR-REV-2, FR-TOUR-2 |
| 4 | Tour step 2, *Watch it fix*: clicks **Fix and test**. A live log streams: Ultra plan → apply → tests fail (1) → Ultra repair → tests pass (148/148). Each step is labelled with its model and duration. | PR view, Fix panel | FR-FIX-* |
| 5 | Tour step 3, *Monday's queue*: four lanes and the attention bar ("41 of your 120 min"). Points at the build-script PR in *Needs another reviewer*, with chips "Build script changed" and "Binary test file added". | Queue | FR-TRI-*, FR-ROUTE-5 |
| 6 | Tour step 4, *Is it really her eye?*: Proof headline bars and the caricature check. | Proof | FR-FID-* |
| 7 | Tour step 5, *Try it yourself*: invites the judge to spot what Mira spotted on one PR (a 1-item practice). Feedback in 10 s. | Practice | FR-GROW-* |
| 8 | Tour ends on Ask with suggested prompts. | Ask | FR-ASK-* |

### J2 · Monday morning: clearing the queue (maintainer)

1. Opens Queue. It is sorted by lane, then by attention. The header shows "12 open · 41 min of your 120".
2. *Handled for you* (5 PRs): each shows "Fixed and tested" or "Reply drafted" (for AI slop). Bulk action: **Export all drafts**.
3. *Needs your eye* (3 PRs): opens the first. The PR view shows the diff with Keeper's notes in the margin, each labelled "Your lens · cites #212". Accepts two, edits one ("too harsh"), dismisses one ("not relevant here"). Clicks **Fix and test** for the accepted one.
4. *Worth a second look* (2 PRs): a note "You've missed this kind of issue before: 2 bugs followed (#301, #355)". Marks it "Good catch".
5. *Needs another reviewer* (2 PRs): clicks **Hand to Theo**; the drafted note is copied to the clipboard.
6. Finishes. A toast: "4 new examples for your lens. Update to v3?" → the lens diff preview → **Update**.

FR: FR-Q-*, FR-REV-*, FR-FB-*, FR-FIX-*, FR-ROUTE-*, FR-LENS-8.

### J3 · Understanding and owning the lens (maintainer)

1. Opens Lens. Sees "Mira's lens · v2 · learned from 612 of your comments on 214 PRs".
2. *What you notice*: cards (for example "Include paths must stay inside the project root", Proven, 23 examples, a 0.81 hit rate).
3. *Where your eye matters most*: the top areas, and "Generic review is enough here: docs/, examples/".
4. *Blind spots worth knowing*, and *Possible bias* ("You ask first-time contributors for extra tests 3× as often for similar changes; outcomes show no difference").
5. *Versions*: v1 → v2 diff ("Started noticing: type hints on public functions").
6. *Growth*: health state *Healthy*, with the explanation.
7. Controls: Pause, Export, Revoke, edit an item's wording, turn an item off.

FR: FR-LENS-*, FR-FIND-*, FR-CAL-*, FR-GROW-7…10, FR-GOV-*.

### J4 · Becoming a successor (contributor)

1. Switches the role picker to "Contributor (Sam)", or a judge chooses "Practise as yourself".
2. Practice → **Start check** (before): 5 held-out PRs, with no Keeper notes visible. Writes or clicks notes on lines. A timer is visible but not enforced.
3. Result: "You caught 3 of 11 things Mira flagged. The costly ones you missed: …". Own valid catches are credited as "Your own eye".
4. **Learn** session: 5 different PRs. For each, the learner reviews first, then gets a coaching hint (not the answer) and one more try, then the reveal: Mira's comments, Keeper's explanation and the lens item.
5. **After** check on a parallel set: "Now 7 of 12 (+33 points). Costly misses: 2 → 0."
6. Progress chart over sessions, and the learner's own lens diff.

FR: FR-GROW-1…6.

### J5 · Proof run (judge or maintainer)

1. Proof → headline from the latest run (the snapshot or a live run).
2. **Run again** shows a cost estimate ("≈ $0.40, about 4 min, uses the Batch API: off"). On confirmation, a live job streams progress.
3. Opens one case: the side-by-side for one held-out PR, with matches drawn between maintainer comments and Keeper or generic notes.
4. Expands "How we measure this": definitions, the split, the judge's agreement with ground truth, confidence intervals, and the falsifiers.

FR: FR-FID-*.

### J6 · Importing a real project (power user, optional)

1. Settings → Projects → **Import from GitHub**: enter `owner/repo` and the maintainer's login, then tick the consent and attribution acknowledgement.
2. A job fetches, ingests and analyses, streaming progress and an estimated cost, and respecting rate limits.
3. The new project appears in the project switcher, with *Imported* badges. Quotes are attributed with links.

FR: FR-IMP-*.

### J7 · Asking (anyone)

- From any screen: **Ask about this** opens a side drawer with the current context attached (for example "PR #412").
- Typical prompts: "Why is #418 in *Needs another reviewer*?", "Show PRs touching the include resolver this month", "Draft a friendly reply asking for a test", "What changed in my lens since v1?", "Run the Proof again" (a confirmation card appears).

FR: FR-ASK-*.
