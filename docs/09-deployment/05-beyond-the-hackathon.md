# Beyond the hackathon

Not in v1. Listed so that v1's design does not block these.

| Direction | What it needs | v1 hooks already in place |
|---|---|---|
| GitHub App (post drafts as suggestions with the maintainer's approval) | OAuth, write scopes, webhook ingestion | Review export as GitHub review JSON; the `Drafted by Keeper` label; the permission layer |
| Live webhook triage | A webhook receiver, a queue | The `triage` job and idempotent analysis per head SHA |
| Multi-maintainer projects | Lens composition, per-person consent UI | Multiple lenses per project; hand-off scoring uses distance between lenses |
| More languages | Recipes, static tools per language | `config/sandbox.yaml` recipes; the baseline tools are config |
| Portable lens (Agent Skills) in other agents | Distribution | Lens export as `SKILL.md` + `lens.json` |
| Cross-model fidelity ("does perspective lose value as AI improves?") | Several ruler generations over time | Rulers are content-hashed and every result references its ruler |
| Real-repository studies | Consent from maintainers, IRB-style process | Consent records, attribution, deletion |
| Self-hosted Nemotron fine-tuned on the residual | GPU endpoint, training job | `openai_compatible` provider; Serverless Jobs runner |
| Workspace auth (real identities) | SSO | `X-Keeper-Role` is already the permission seam |
