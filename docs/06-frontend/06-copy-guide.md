# Copy guide

## 1. Voice

- **Plain and short.** Sentences ≤ 20 words in the UI. No jargon in labels; jargon only in tooltips and in "How this works".
- **Concrete.** Name the PR, the person, the file and the number: "Mira flagged this on #233", not "Historical signal detected".
- **Honest.** Say when Keeper is unsure ("Possible"), when results are saved, when something failed. Never overclaim ("proves", "always").
- **Kind about people.** Findings describe code, not authors. Slop replies are polite. Practice never scolds.
- **Keeper drafts; people decide.** Use "Suggested", "Drafted by Keeper", "Keeper won't guess here". Never "Keeper approved".

## 2. Fixed vocabulary

| Concept | UI word | Never |
|---|---|---|
| `edge` lane | Needs your eye | R+, residual |
| `blind_spot` | Worth a second look | R−, your weakness |
| `shared` | Handled for you | Auto-approved |
| `unknown` | Needs another reviewer | Unknown, error |
| `baseline_only` | Other model notes | — |
| Lens | {Name}'s lens | Profile, model of you |
| Baseline | Generic review (same model, no lens) | GPT, the AI |
| Fidelity Test | Proof | — |
| Growth Test | Practice; "the Growth Test" in its title | Exam |
| Lens item | Something {Name} notices; "pattern" in lists | Rule |
| Analysis | Keeper's read of this PR | Scan |

Glossary entries (tooltips) live in `config/glossary.yaml` (served by `GET /glossary`, also used by the assistant): `key`, `label`, `short` (≤ 15 words), `long_md`.

## 3. Templates

All UI strings are in `frontend/src/copy/en.json` with ICU-style placeholders: `"queue.answer.some": "{need, plural, one {# of {total} pull requests needs you} other {# of {total} pull requests need you}} · about {minutes} min of your {budget}-min week"`. Names, numbers and PRs are always variables; no example values are in the copy file.

Server-generated prose (summaries, lens card, hand-off notes) comes from prompts that follow the same voice rules (each prompt includes `config/prompts/_voice.md`).

## 4. Numbers and uncertainty

- Percentages are whole numbers in the UI; intervals are in parentheses: "61% (48–72)".
- Confidence words (from the categorical confidence in [Applying the lens](../02-methodology/06-applying-the-lens.md) §3): `high` "Likely", `medium` "Possible", `low` "Worth checking". The mapping is in `copy/en.json` `confidence.*`; the tooltip explains how it was derived ("Based on a pattern proven in 9 past reviews").
- Small samples: if n < 10, add "(small sample)".
