# Security & responsible-AI checklist

**Access & least privilege**
- [ ] Service identity has only the scopes the tools need; read and write separated
- [ ] No credentials in prompts, code or logs; secrets stored in the platform's secret store
- [ ] Write tools are idempotent (stable request IDs) so retries cannot duplicate documents

**Policy enforcement**
- [ ] Limits (value, quantity, scope, rate) enforced *below* the model, in the tool layer
- [ ] Human approval path exists for high-impact actions; default is deny
- [ ] Outcome reported to the user comes from tool results, not from model claims

**Prompt injection & data handling**
- [ ] Tool outputs and retrieved documents are treated as data; adversarial strings are in the eval set
- [ ] Personal/confidential data minimised in prompts; DPIA/approval obtained where required
- [ ] Logs are access-controlled; retention matches policy

**Quality & transparency**
- [ ] Agent states what it did and cites sources/tool results; can say "I don't know"
- [ ] Evaluation covers direct, paraphrased and adversarial cases; thresholds agreed with the business
- [ ] Known limitations documented for users (what it cannot do, when to escalate)

**Operations**
- [ ] Monitoring for refusals, errors, DLQ depth, cost; alert owners named
- [ ] Rollback tested; model/prompt versions recorded with each release
