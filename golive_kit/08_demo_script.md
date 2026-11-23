# 10-minute demo script

*Every step below runs from this repo; numbers quoted should come from `results/` or the eval reports, not memory.*

| Min | Show | Say |
|---|---|---|
| 0-1 | The business problem and success metrics (from the spec) | "Here is what we agreed to measure." |
| 1-3 | Agent answers a stock question, then does a conditional reorder (Project 1 REPL or MCP host) | "It checks stock first and only orders if it is below the reorder point." |
| 3-4 | Ask for a EUR 10k+ order | "Policy is enforced below the model: it is held for approval and the user is told why." |
| 4-6 | Show the audit trail / tool-call trace | "Every action is logged with arguments and outcome." |
| 6-8 | Run `python -m integration.simulate`; show retry vs no-retry and the duplicate count with/without idempotency | "Flaky backend, duplicate messages: nothing lost, nothing doubled." |
| 8-9 | Show the eval report tiers, including where the baseline fails | "We measure honestly - paraphrases are the gap the model must close." |
| 9-10 | What is deployed vs not yet, next steps | "Next: connect to your sandbox, add your policies, run your scenarios." |

## Questions to expect
- *Can it order something it should not?* -> guardrail tests + red-team results.
- *What if the backend is down or sends duplicates?* -> simulation results.
- *How do we know a prompt/model change did not regress it?* -> eval gate in CI.
- *What is not done yet?* -> be explicit (real backend mapping, live model, platform deployment).
