# Functional specification - <Use case name>

| | |
|---|---|
| Version / date | |
| Business owner / IT owner | |
| Status | Draft / Reviewed / Approved |

## 1. Business context
*Two paragraphs: the problem, today's cost, the target outcome. Include volumes.*

## 2. Scope
| In scope | Out of scope |
|---|---|
| | |

## 3. User stories & acceptance criteria
| ID | Story | Acceptance criteria (testable) |
|---|---|---|
| UC-1 | As a ... I can ... so that ... | Given/When/Then, with concrete values |

## 4. Agent behaviour
- **Tools** (name, inputs, outputs, read/write, owning system)
- **Planning approach** (model, prompt strategy, step limit)
- **Clarification rules** (when it must ask rather than act)

## 5. Guardrail policy
| Rule | Value | Outcome when breached (deny / ask human / log) |
|---|---|---|

## 6. Integration design
| Source/target | Interface (REST/OData/event) | Auth | Mapping doc | Error handling (retry / DLQ / idempotency) |
|---|---|---|---|---|

## 7. Non-functional requirements
Latency, availability, audit retention, data residency, cost per request budget.

## 8. Evaluation plan
Eval set size and tiers, pass thresholds per tier, who reviews failures, how regressions block release.

## 9. Open items and decisions log
| # | Question / decision | Owner | Due | Status |
|---|---|---|---|---|
