# Frontend

Keeper's frontend is for someone who has never seen it before, such as a judge with ten minutes. It should explain itself. Every screen answers one question in plain words, shows the answer first, and offers one obvious next step.

| Document | What it covers |
|---|---|
| [UX principles and information architecture](01-ux-principles-and-ia.md) | The rules, the six destinations, what is combined and what is separate, and why |
| [Design system](02-design-system.md) | Tokens (colour, type, space, radius, motion), the lane colour language, themes |
| [Responsive layout](03-responsive-layout.md) | Fluid sizing, container queries, layouts per width, the viewport test matrix |
| [App shell, navigation and the guided tour](04-app-shell-and-tour.md) | The shell, the top bar, the role picker, the live/saved badge, banners, the tour |
| [Screens: Queue](screens/01-queue.md) | Home: the triaged queue |
| [Screens: Pull request](screens/02-pull-request.md) | One PR: findings by lane, diff, compare, review draft, fix and test, hand-off |
| [Screens: Ask](screens/03-ask.md) | Chat with Keeper |
| [Screens: Lens](screens/04-lens.md) | The maintainer's lens: card, items, where it matters (Find), versions, growth, controls |
| [Screens: Proof](screens/05-proof.md) | The Fidelity Test |
| [Screens: Practice](screens/06-practice.md) | The Growth Test, as practice |
| [Screens: Settings](screens/07-settings.md) | Models, usage, sandbox, projects, preferences |
| [Screens: First run, empty and error states](screens/08-first-run-and-states.md) | First run, no key, loading, empty, errors |
| [Component catalog](05-component-catalog.md) | Every shared component with its props and behaviour |
| [Copy guide](06-copy-guide.md) | Words, tone and the string file |
| [Accessibility](07-accessibility.md) | WCAG 2.2 AA requirements and tests |

Stack: see [System architecture](../04-architecture/01-system-architecture.md) §2. Source root: `frontend/src/` (layout in [Repository structure](../10-build/01-repository-structure.md)).
