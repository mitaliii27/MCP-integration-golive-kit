# Hypercare plan (first 2-4 weeks)

| Area | Practice |
|---|---|
| Coverage | Named developer + IT contact during business hours; escalation path documented |
| Daily review (15 min) | Refusals and clarifications, dead-letter queue, top failure reasons, any approval-required cases and their outcomes |
| Weekly review | Metrics vs success criteria from the spec; user feedback; backlog of eval cases to add from real failures |
| Feedback loop | Every real failure becomes an eval case *before* the fix |
| Change control | Prompt/model/threshold changes go through the same eval gate as code |
| Exit criteria | Metrics stable for 2 consecutive weeks; no open high issues; support handed to the run team with a runbook |

## Metrics to track
- Task success rate on real traffic (sampled and human-reviewed)
- Policy violations (target: 0) and approval-required rate
- Clarification rate (too high = unclear prompts or missing data)
- Dead-letter depth and age; retry rate; duplicate suppressions
- Latency p50/p95 and cost per request
- User-reported problems per 100 requests
