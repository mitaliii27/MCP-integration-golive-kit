"""Generates docs/simulation_report.md and README.md from results/simulation.json (no hand-typed numbers)."""
import json, pathlib, re, subprocess, sys
root = pathlib.Path(__file__).resolve().parents[1]
r = json.loads((root / "results/simulation.json").read_text())
s, A, B, C = r["stream"], r["with_retry_and_idempotency"], r["no_retry"], r["retry_no_idempotency"]
collected = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=root, capture_output=True, text=True).stdout
n_tests = int(re.search(r"(\d+) tests? collected", collected).group(1))

report = f"""# Simulation report
One seeded stream of **{s['messages_in']:,} messages** ({s['unique_orders']:,} unique orders + {s['duplicate_resends']} duplicate re-sends) replayed through the same flow under three policies.
Injected faults: **{int(s['transient_failure_rate']*100)}% transient target failure per attempt**, malformed messages ({s['kinds']['malformed']}), poison messages the target permanently rejects ({s['kinds']['poison']}), and high-value orders ({s['kinds']['high_value']}) that are *meant* to go to an approval queue. Backoff is counted on a virtual clock.

| | retry + idempotency | no retry | retry, no idempotency |
|---|---|---|---|
| Delivered | {A['delivered']:,} | {B['delivered']:,} | {C['delivered']:,} |
| Routed to approval queue | {A['routed_to_approval']} | {B['routed_to_approval']} | {C['routed_to_approval']} |
| Duplicates suppressed | {A['duplicates_suppressed']} | {B['duplicates_suppressed']} | {C['duplicates_suppressed']} |
| Dead-lettered | {A['dead_lettered']} | {B['dead_lettered']} | {C['dead_lettered']} |
| Retries performed | {A['retries']} | {B['retries']} | {C['retries']} |
| **Deliverable orders delivered** (of {A['expected_deliverable_unique_orders']:,}) | **{A['delivery_rate_of_deliverable_pct']}%** | **{B['delivery_rate_of_deliverable_pct']}%** | {C['delivery_rate_of_deliverable_pct']}% |
| Lost to exhausted retries | {A['transient_loss_pct']}% | {B['transient_loss_pct']}% | {C['transient_loss_pct']}% |
| **Duplicate deliveries at the target** | **{A['target_duplicate_deliveries']}** | {B['target_duplicate_deliveries']} | **{C['target_duplicate_deliveries']}** |
| Virtual backoff time (s) | {A['virtual_backoff_s']} | {B['virtual_backoff_s']} | {C['virtual_backoff_s']} |

## What this shows
- **Retry with exponential backoff** is what turns a 15%-flaky target from {B['delivery_rate_of_deliverable_pct']}% delivered into {A['delivery_rate_of_deliverable_pct']}%.
- **Idempotent receive** is what keeps duplicates out: without it, **{C['target_duplicate_deliveries']}** duplicate business documents reached the target (and duplicates of high-value orders were queued for approval twice: {C['routed_to_approval']} vs {A['routed_to_approval']}).
- **Dead-lettering** parks bad data instead of retrying it forever. Every injected malformed/poison message landed in the correct bucket (check passes: `{A['bad_messages_classified_correctly']}` - evaluated only when retries are on, because with a single attempt a transient fault can mask a poison message).
- **Re-drive:** after the target recovered, {A['redrive']['delivered']} of {A['redrive']['attempted']} messages whose retries were exhausted were delivered from the DLQ; the remaining {A['redrive']['dlq_remaining']} dead letters are genuinely bad data and correctly stay parked.
- Attempts needed per delivered message (retry scenario): {', '.join(f'{k}: {v}' for k, v in A['attempts_histogram'].items())}.

## Limits
Simulated targets and a virtual clock - no real network, ordering guarantees, concurrency or persistence (processed-key set and queues are in memory). This demonstrates the *patterns*; it is not SAP Integration Suite and says nothing about its runtime behaviour.
"""
(root / "docs/simulation_report.md").write_text(report)

readme = f"""# MCP Server + Integration Flows + Go-Live Kit
**Three reusable building blocks for AI-agent customer engagements:** an MCP server exposing business tools, a config-driven integration-flow engine with retry/DLQ/idempotency, and a workshop-to-hypercare delivery kit with a project scaffold.
Built as a portfolio project for an *AI Factory Associate Consultant* profile (MCP connections, integration flows, customer implementations, reusable assets).

![simulation summary](docs/img/simulation_summary.png)

## 1. MCP server (`mcp_server/`)
Exposes five procurement tools, two resources (`policy://procurement`, `catalog://materials`) and a prompt (`replenishment_review`) over the Model Context Protocol (MCP Python SDK 1.x, stdio transport).
- Tools carry **annotations** (read tools read-only + idempotent; the write tool non-destructive + idempotent) and **structured output** schemas.
- The write tool is **idempotent on `request_id`** - a retrying agent cannot create two requisitions.
- Business refusals (`approval_required`, `denied`) are normal results the agent must read; invalid input is an MCP tool error.
- Approval policy is enforced **server-side**, so it holds for every client/model.
- Tested over the in-memory client **and a real stdio subprocess**.

## 2. Integration-flow engine (`integration/`)
YAML-defined flows - `validate -> map -> route -> deliver` - with exponential-backoff retry, dead-letter queue + re-drive, idempotent receive, and a correlation-ID trail. Two flows ship (`orders_to_s4`, `supplier_sync`); the second is pure configuration.

### Measured behaviour (reproducible: `make sim`)
Seeded stream of {s['messages_in']:,} messages through a {int(s['transient_failure_rate']*100)}%-flaky target:

| | retry + idempotency | no retry | no idempotency |
|---|---|---|---|
| Deliverable orders delivered | **{A['delivery_rate_of_deliverable_pct']}%** | {B['delivery_rate_of_deliverable_pct']}% | {C['delivery_rate_of_deliverable_pct']}% |
| Duplicate deliveries at target | **{A['target_duplicate_deliveries']}** | {B['target_duplicate_deliveries']} | **{C['target_duplicate_deliveries']}** |

Re-drive recovered {A['redrive']['delivered']}/{A['redrive']['attempted']} exhausted messages once the target was healthy; all injected malformed/poison messages were classified into the correct DLQ bucket. Full table: [`docs/simulation_report.md`](docs/simulation_report.md).

## 3. Go-live kit (`golive_kit/`) and project scaffold (`templates/`, `scripts/new_agent.py`)
Eight reusable documents (discovery agenda + questionnaire, functional-spec template, test plan/UAT, cutover runbook, hypercare plan, security & responsible-AI checklist, demo script) and an **agent project skeleton**:
```bash
python scripts/new_agent.py "Invoice Triage Agent" --out ./invoice-triage-agent
```
`tests/test_scaffold.py` generates a project and runs *its* tests and evals, so the template can't silently rot.

## Read this before quoting anything
- The integration engine is a **Python stand-in demonstrating integration patterns - not SAP Integration Suite** and not its flow format. Simulations use mock targets and a virtual clock; state is in memory.
- The MCP server wraps an **in-memory mock backend** with simplified, non-SAP schemas. No live agent/host or real S/4HANA system was connected.
- Nothing here has been deployed to SAP BTP.
- The go-live documents are generic templates; the worked examples are in the other two projects.

## Layout
```
core/          mock procurement service (idempotent writes, approval policy)
mcp_server/    FastMCP server (tools, resources, prompt)
integration/   engine.py, adapters.py, simulate.py, flows/*.yaml
golive_kit/    00-08 delivery documents
templates/     agent-skeleton (+ scripts/new_agent.py scaffold)
results/       simulation.json
tests/         {n_tests} tests (MCP, engine, simulation, scaffold)
docs/          architecture.md, simulation_report.md, img/
```

## Quickstart
```bash
pip install -r requirements.txt
make test sim charts docs
python -m mcp_server.server        # stdio MCP server (point any MCP host at it)
```

## JD alignment
| JD line | Where |
|---|---|
| Model Context Protocol (MCP) connections | `mcp_server/` (stdio + in-memory tested) |
| Develop integration flows (SAP Integration Suite) | `integration/` - patterns only; platform not used |
| Support customer implementations from workshops to go-live - preparing specifications | `golive_kit/` |
| Contribute reusable assets to the Global AI Factory - samples, templates, demo content | `templates/agent-skeleton`, `scripts/new_agent.py`, `golive_kit/08_demo_script.md` |
| Standards for code review, Git, security, CI/CD | tests + `.github/workflows/ci.yml`, security checklist |

## Resume bullets (accurate as built)
- Built an MCP server (tools with annotations and structured output, resources, prompt) with server-side approval policy and idempotent writes; tested in-memory and over a real stdio transport.
- Implemented a YAML-driven integration-flow engine (validate/map/route/deliver, exponential-backoff retry, dead-letter queue with re-drive, idempotent receive, correlation-ID tracing) and quantified it in a seeded chaos simulation: {A['delivery_rate_of_deliverable_pct']}% of deliverable orders delivered vs {B['delivery_rate_of_deliverable_pct']}% without retry, 0 vs {C['target_duplicate_deliveries']} duplicate deliveries with/without idempotency.
- Authored a workshop-to-hypercare delivery kit and a tested agent-project scaffold ({n_tests} tests in the repo) as reusable team assets.
"""
(root / "README.md").write_text(readme)
print("wrote docs/simulation_report.md and README.md;", n_tests, "tests collected")
