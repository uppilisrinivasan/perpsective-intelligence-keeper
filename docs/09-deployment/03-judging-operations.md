# Judging operations (30 Oct – 15 Dec 2026)

Judges must be able to use the demo **free and without restriction until 15 Dec 2026, 12:00 PST** (Hackathon ref 03 §3). Keep it running until 15 Dec, 23:59 PT.

## 1. Before submitting (by 29 Oct)

- [ ] Deployed from the **submission tag** (`v1.0.0`); smoke test passed ([Deployment steps](02-nebius-deployment-steps.md) §8) from a fresh incognito window.
- [ ] Token Factory balance funded for the window (spend cap × days, plus margin); note the Builders credit expiry date (reportedly 90 days after issue).
- [ ] `KEEPER_SPEND_CAP_USD` per day is set so the balance cannot run out before 15 Dec: `daily_cap ≤ balance / days_remaining`.
- [ ] Access codes created (one for judges, one for the team) and put in the Devpost testing instructions.
- [ ] Model probe green for all roles; fallbacks tested by temporarily setting a bad model ID in a staging deployment.
- [ ] The saved snapshot in the image matches the video (same data manifest).

## 2. Monitoring

| What | How | Frequency |
|---|---|---|
| Uptime | An external HTTP check on `/api/v1/health` (any free uptime monitor) alerting by e-mail | every 5 min |
| Model availability | `/api/v1/status` probe result; an alert if any role is in fallback | daily (scripted: `infra/nebius/check_status.sh`) |
| Spend | Settings → Usage, or `GET /api/v1/usage?period=day` | daily |
| Token Factory model list changes | Compare `GET /v1/models` with `config/models.yaml` (part of `check_status.sh`) | daily |
| Errors | `nebius ai endpoint logs <id>` filtered by `level=ERROR` | daily |

## 3. Runbook

| Event | Action |
|---|---|
| Endpoint down | `nebius ai endpoint get <id>`; restart (stop and start); if the image is broken, redeploy the submission tag |
| A model ID removed | The fallback chain keeps the app live. Update `KEEPER_MODEL_*` (an `--env` change and redeploy) to the replacement model; note it in the README's changelog ("Changed after submission: model ID only, because Token Factory removed X on <date>") |
| Balance low or 402 | Top up; the app shows saved results and a banner meanwhile (live remains the default path once funded) |
| Daily cap reached early | Inspect usage by feature; if abuse, rotate the access code (SecretStash new version, redeploy) |
| Sandboxes beta unstable | Switch `SANDBOX_PROVIDER=local` (env change); Settings states it |
| A bug found by a judge | Fix only critical bugs; tag `v1.0.x`; keep the default branch stable; document the change in the README |

## 4. Cost log

Keep `docs/09-deployment/cost-log.md` (created during operations) with dates, endpoint hours, Token Factory spend and balance, for the feedback section and for the post-mortem.

## 5. After 15 Dec

Teardown per [Deployment steps](02-nebius-deployment-steps.md) §9; revoke the deployment key; keep the repository public.
