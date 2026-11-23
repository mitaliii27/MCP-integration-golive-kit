# Cutover runbook

**Principle:** go live to a small, reversible slice first (one team, one plant, one document type), with write actions behind the approval policy.

## T-5 to T-1 days
- [ ] Release candidate frozen; eval + red-team run on the exact build (attach results)
- [ ] Production credentials issued to a *service identity* with least privilege; rotation date recorded
- [ ] Audit log destination and retention confirmed; alerts configured
- [ ] Rollback procedure rehearsed (see below); owner named
- [ ] Users briefed: what it does, what it refuses, how to escalate

## Go-live day
| Step | Owner | Check |
|---|---|---|
| 1. Deploy to production, feature flag OFF | Dev | Health endpoint OK |
| 2. Smoke test with read-only tools | Dev + IT | Expected data returned |
| 3. Enable for pilot users only | Delivery lead | Pilot list verified |
| 4. Enable write tools with approval threshold at conservative value | Business owner | First write reviewed by a human |
| 5. Watch dashboards for 2 hours | Dev + IT | Error rate, refusals, latency, DLQ depth |

## Rollback triggers (any one => disable the flag, revert to manual process)
- Any policy violation (a write that should have been blocked)
- Duplicate business documents created
- Error rate or DLQ depth above agreed threshold for 15 minutes
- Security finding rated high

## Rollback steps
1. Turn the feature flag OFF (agent stops accepting requests).
2. Pause integration consumers; leave messages in the queue (do not drop).
3. Notify business owner and users via the agreed channel.
4. Triage dead-lettered and in-flight items; re-drive after fix using the idempotent re-drive procedure.
5. Write the incident summary within 24 hours.
