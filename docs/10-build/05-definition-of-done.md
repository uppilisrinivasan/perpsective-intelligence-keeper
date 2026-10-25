# Definition of done

## 1. For any change

- [ ] It implements the cited requirement(s) and follows the relevant docs (or updates them).
- [ ] Tests are added or updated; `./run.sh --test` is green.
- [ ] Lint, types and import contracts pass.
- [ ] No hardcoded values (the guard is green); no secrets (gitleaks is green).
- [ ] User-facing text is in `copy/en.json`, in the voice of the [Copy guide](../06-frontend/06-copy-guide.md).
- [ ] Works in no-key mode (or shows the designed `KeyRequired` state).
- [ ] UI changes: keyboard-operable, axe-clean, no horizontal scroll at the viewport matrix, primary action visible from 1280×720.

## 2. For a backend feature

- [ ] Every model call goes through the gateway with a prompt file, a versioned entry in `versions.lock`, and an output schema.
- [ ] The cost of the action is estimated and confirmable if it can exceed auto-approve.
- [ ] Long work runs as a job with step events.
- [ ] The endpoint is in OpenAPI with typed request and response, error codes and permissions.
- [ ] Results carry provenance (origin, ruler, lens version, models).

## 3. For a screen

- [ ] It has the answer header, one primary action, and the designed loading, empty, error and saved states.
- [ ] It works at every width in the matrix, using container queries.
- [ ] Deep links work (refresh keeps the state).
- [ ] "Ask about this" is available where the IA says so.
- [ ] Glossary terms have tooltips.

## 4. For the release (v1.0.0)

- [ ] R0–R5 gates in [Scope](../01-business/05-scope-and-release-plan.md) §3 are met.
- [ ] A clean clone runs with `./run.sh` on macOS and Linux, in no-key and live mode.
- [ ] `data/` is committed, validated and within the size budget; the manifest verifies.
- [ ] `./run.sh --eval` meets `config/eval.yaml`; the Proof run in the snapshot passes or its failure is reported honestly.
- [ ] The deployed URL passes the smoke test; the spend cap and access codes are set.
- [ ] README, video, Devpost form and feedback are complete ([Submission](../09-deployment/04-hackathon-submission.md)).
- [ ] The BRD acceptance checklist ([BRD](../01-business/01-business-requirements.md)) is ticked.
