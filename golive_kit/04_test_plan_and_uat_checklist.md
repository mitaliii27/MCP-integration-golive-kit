# Test plan & UAT checklist

## Test levels
| Level | What | Gate |
|---|---|---|
| Unit | Tools, guardrails, mappings, client retries | 100% of tests pass in CI |
| Integration | Agent <-> real/sandbox APIs, DLQ and retry behaviour under injected faults | No lost or duplicated business documents |
| Agent evaluation | Direct / paraphrased / adversarial case tiers against the chosen model | Pass thresholds in the spec; **zero policy violations** |
| Security | Prompt-injection cases, least-privilege review, secret scanning | No open high findings |
| Performance | p95 latency and cost per request at expected peak | Within spec budget |
| UAT | Real users, real (anonymised) cases | Sign-off checklist below |

## Release gate (must all be true)
- [ ] CI green on the release commit (tests + eval gate)
- [ ] Eval thresholds met on the *customer's* scenarios, not only the sample set
- [ ] Policy-violation count = 0 across eval and red-team runs
- [ ] Every "must never" statement from discovery has a test
- [ ] Rollback tested in a non-production environment
- [ ] Monitoring and alerts live; on-call named

## UAT checklist (per scenario)
| # | Scenario | Expected | Actual | Pass/Fail | Tester | Notes |
|---|---|---|---|---|---|---|
| 1 | Happy path | | | | | |
| 2 | Missing information -> agent asks | | | | | |
| 3 | Above-threshold action -> human approval | | | | | |
| 4 | Backend unavailable -> graceful message, no duplicate writes | | | | | |
| 5 | Out-of-scope request -> polite refusal | | | | | |
| 6 | Hostile/injected text inside data | | | | | |

**Sign-off:** business owner ____  IT owner ____  security ____  date ____
