# Simulation report
One seeded stream of **5,250 messages** (5,000 unique orders + 250 duplicate re-sends) replayed through the same flow under three policies.
Injected faults: **15% transient target failure per attempt**, malformed messages (143), poison messages the target permanently rejects (57), and high-value orders (303) that are *meant* to go to an approval queue. Backoff is counted on a virtual clock.

| | retry + idempotency | no retry | retry, no idempotency |
|---|---|---|---|
| Delivered | 4,495 | 3,810 | 4,727 |
| Routed to approval queue | 303 | 303 | 321 |
| Duplicates suppressed | 250 | 218 | 0 |
| Dead-lettered | 202 | 919 | 202 |
| Retries performed | 836 | 0 | 870 |
| **Deliverable orders delivered** (of 4,497) | **99.96%** | **84.72%** | 99.98% |
| Lost to exhausted retries | 0.044% | 16.166% | 0.044% |
| **Duplicate deliveries at the target** | **0** | 0 | **231** |
| Virtual backoff time (s) | 491.0 | 0.0 | 508.5 |

## What this shows
- **Retry with exponential backoff** is what turns a 15%-flaky target from 84.72% delivered into 99.96%.
- **Idempotent receive** is what keeps duplicates out: without it, **231** duplicate business documents reached the target (and duplicates of high-value orders were queued for approval twice: 321 vs 303).
- **Dead-lettering** parks bad data instead of retrying it forever. Every injected malformed/poison message landed in the correct bucket (check passes: `True` - evaluated only when retries are on, because with a single attempt a transient fault can mask a poison message).
- **Re-drive:** after the target recovered, 2 of 2 messages whose retries were exhausted were delivered from the DLQ; the remaining 200 dead letters are genuinely bad data and correctly stay parked.
- Attempts needed per delivered message (retry scenario): 1: 3788, 2: 605, 3: 90, 4: 12.

## Limits
Simulated targets and a virtual clock - no real network, ordering guarantees, concurrency or persistence (processed-key set and queues are in memory). This demonstrates the *patterns*; it is not SAP Integration Suite and says nothing about its runtime behaviour.
