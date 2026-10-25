# Screen: Practice

**Question answered:** "Can I learn to notice what the maintainer notices?" **Primary action:** **Try one PR** (the taste test) for a first-time visitor; **Continue** for a returning learner. **Requirements:** FR-GROW. Method: [Growth Test](../../02-methodology/12-growth-test-and-health.md) Part A.

## 1. Landing (`/practice`)

```
Practise noticing like Mira
Review a real past PR without help, then see what Mira caught and why.

 ┌ Try one PR · 5 min ─────────────┐  ┌ The Growth Test · about 45 min ───────────────────────┐
 │ A 1-PR taste test.               │  │ 1. Before: 5 PRs on your own                         │
 │ Not a test, just a feel for it.  │  │ 2. Learn: 5 PRs with hints, then Mira's answers       │
 │ [Try one PR]                     │  │ 3. After: 5 different PRs on your own                 │
 └──────────────────────────────────┘  │ [Start: Before]                                       │
                                       └───────────────────────────────────────────────────────┘
 Your progress (if any): Before ✓ 32% · Learn ✓ · After —      Learner: Me (judge) ▾
```

The learner is from the role picker. "Me (judge)" uses a guest key, kept in a cookie, so judges' sessions are separate. In demo mode, Sam (contributor) has saved sessions, which show a complete before/learn/after example.

## 2. Item view (`/practice/:sessionId/:index`)

```
Before · PR 2 of 5                                                  [Exit, progress is saved]
#287 Allow merging lists by key
<description>
┌ Diff (full width, notes in the gutter) ─────────────────────────────────────────────────────┐
│  12 + def merge_lists(a, b, key):            [+] ← click the gutter to add a note on a line  │
│      ┌ Your note ───────────────────────────────────────────────────┐                        │
│      │ What happens when key is missing in one item?                │ [Save] [Delete]        │
│      └──────────────────────────────────────────────────────────────┘                        │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
General notes about this PR: [ … ]
                                                    [Submit my review] (primary)
```

- Uses `DiffView` in **practice mode**: no Keeper findings, no lens hints, no "Ask about this" (the Ask drawer is hidden during before and after, matching "test without the tool").
- Notes are kept locally (local storage) until submitted, so a refresh doesn't lose them.
- After submitting:
  - **before, after:** "Saved. Next PR". There is no feedback until the session ends (to keep the forms clean).
  - **learn, attempt 1:** `HintList` (one hint per missed costly finding, pointing to where and what kind of thing), then **Try again**.
  - **learn, attempt 2, and taste:** the **Reveal** (below).

## 3. Reveal

```
You caught 1 of 3 things Mira raised.
 ✓ Missing key handling        — your note on line 12 matched Mira's comment ▸
 ✗ Order isn't stable          — why it matters: two merges in a row give different results (lens: "Deterministic merges", seen 7×)
 ✗ No test for duplicate keys  — …
 ★ You also noticed: "docstring says list, code accepts tuple" — valid, and Mira didn't mention it
 · "rename variable b" — not an issue here
[Next PR]
```

Mira's comments are shown attributed, with links. The words never flatter or scold; they state facts. Own-eye catches get a star and are never counted against the learner.

## 4. Results

- After a session: `SessionResult` with recall, costly misses and own-eye counts, in plain words.
- After `after`: `GrowthResult`, before against after (bars), the growth in recall and costly misses, the caveat "5 PRs per form: indicative, not definitive", and the **learner lens diff** ("Started catching: deterministic merges · Still missing: include-path escapes"). If own-eye fell while recall rose, the "Keep your own eye too" note appears.
- Links: "Ask: what should I practise next?" and "See Mira's lens".

## 5. States

- No items (imported project without enough held-out PRs): "Not enough past reviews to build practice PRs yet."
- No key: the taste test and saved sessions work. Saved scoring exists only for the snapshot's items and learner, so live scoring for new notes shows "Scoring needs a Nemotron API key", with Mira's comments still revealed (the reveal itself needs no model).
