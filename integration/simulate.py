"""Chaos simulation: one seeded message stream replayed through the engine under different policies.

    python -m integration.simulate        # writes results/simulation.json

Injected faults (all seeded): 15% transient target failure per attempt, 3% malformed messages,
1% poison messages the target permanently rejects, 5% duplicate re-sends. ~6% of orders are
high-value and legitimately routed to an approval queue instead of the target.
Backoff is accounted on a virtual clock (no real sleeping).
"""
import copy
import json
import random
from collections import Counter
from pathlib import Path

from .adapters import MockTarget
from .engine import Engine, FlowDef, RetryPolicy

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "integration" / "flows" / "orders_to_s4.yaml"
MALFORMED = ("missing_customer", "empty_lines", "negative_total", "bad_qty")


def make_stream(n: int = 5000, seed: int = 1):
    rng = random.Random(seed)
    msgs, kinds = [], {}
    for i in range(n):
        oid = f"ORD-{i:05d}"
        p = {"order_id": oid, "customer": {"id": f"c{rng.randint(1, 400)}"}, "currency": "EUR",
             "total": round(rng.uniform(20, 9000), 2), "lines": [{"sku": f"mat-{rng.randint(1001, 1024)}", "qty": str(rng.randint(1, 50))}
                                                                  for _ in range(rng.randint(1, 4))]}
        r = rng.random()
        if r < 0.03:
            kind = rng.choice(MALFORMED); kinds[oid] = f"malformed:{kind}"
            if kind == "missing_customer": p["customer"] = {}
            elif kind == "empty_lines": p["lines"] = []
            elif kind == "negative_total": p["total"] = -5
            else: p["lines"][0]["qty"] = "many"
        elif r < 0.04:
            p["lines"][0]["sku"] = "bad-0000"; kinds[oid] = "poison"
        elif r < 0.10:
            p["total"] = round(rng.uniform(10001, 60000), 2); kinds[oid] = "high_value"
        else:
            kinds[oid] = "clean"
        msgs.append(p)
    dupes = [copy.deepcopy(m) for m in rng.sample([m for m in msgs if kinds[m["order_id"]] in ("clean", "high_value")], k=int(n * 0.05))]
    stream = msgs[:]
    for d in dupes:
        stream.insert(rng.randint(stream.index(next(m for m in stream if m["order_id"] == d["order_id"])) + 1, len(stream)), d)
    return stream, kinds, len(dupes)


def run(stream, kinds, *, max_attempts=4, idempotent=True, transient=0.15, seed=7, redrive=False):
    flow = FlowDef.from_yaml(FLOW)
    flow.retry = RetryPolicy(max_attempts=max_attempts, backoff_s=0.5, factor=2.0, max_backoff_s=8.0)
    target = MockTarget("SalesOrder", transient_rate=transient, seed=seed,
                        reject=lambda p: "unknown material" if any(i["Material"].startswith("BAD") for i in p["Items"]) else None)
    eng = Engine(flow, {"s4_orders": target}, idempotent=idempotent)
    outcomes = [eng.process(copy.deepcopy(m)) for m in stream]
    unique = {k: v for k, v in kinds.items()}
    expected_deliverable = sum(v == "clean" for v in unique.values())
    res = {
        "messages_in": len(stream),
        "delivered": eng.stats["delivered"], "routed_to_approval": eng.stats["routed"],
        "duplicates_suppressed": eng.stats["duplicate"], "dead_lettered": eng.stats["dead_lettered"],
        "dlq_by_reason": dict(Counter(f"{d.stage}/{d.reason.split(':')[0]}" for d in eng.dlq)),
        "retries": eng.stats["retries"], "virtual_backoff_s": round(eng.virtual_wait_s, 1),
        "attempts_histogram": {str(k): v for k, v in sorted(eng.attempt_histogram.items())},
        "target_duplicate_deliveries": target.duplicate_deliveries, "target_send_calls": target.send_calls,
        "expected_deliverable_unique_orders": expected_deliverable,
        "delivery_rate_of_deliverable_pct": round(100 * (len(target.received) - target.duplicate_deliveries) / expected_deliverable, 2),
        "transient_loss_pct": round(100 * sum(d.reason == "retries_exhausted" for d in eng.dlq) / expected_deliverable, 3),
    }
    # classification check: every injected-bad message must land in the right DLQ bucket, nothing else may be dead-lettered
    exp_bad = Counter()
    seen = set()
    for m in stream:
        oid = m["order_id"]
        if oid in seen: continue
        seen.add(oid)
        k = kinds[oid]
        if k.startswith("malformed"): exp_bad["map/bad_qty" if k.endswith("bad_qty") else "validate/required_or_rule"] += 1
        elif k == "poison": exp_bad["deliver/permanent"] += 1
    got = Counter()
    for d in eng.dlq:
        if d.reason == "retries_exhausted": continue
        key = "deliver/permanent" if d.reason.startswith("permanent") else ("map/bad_qty" if d.stage == "map" else "validate/required_or_rule")
        got[key] += 1
    if max_attempts > 1:   # with a single attempt a transient fault can mask a poison message, so the check is not meaningful
        res["injected_bad_by_bucket"], res["dlq_non_transient_by_bucket"] = dict(exp_bad), dict(got)
        res["bad_messages_classified_correctly"] = exp_bad == got
    if redrive:
        target.transient_rate = 0.0
        pending = [d for d in eng.dlq if d.reason == "retries_exhausted"]
        out = eng.redrive(only=lambda d: d.reason == "retries_exhausted")
        res["redrive"] = {"attempted": len(pending), "delivered": sum(o.status == "delivered" for o in out),
                          "dlq_remaining": len(eng.dlq)}
    return res


def main():
    stream, kinds, n_dupes = make_stream()
    out = {"stream": {"messages_in": len(stream), "unique_orders": len(kinds), "duplicate_resends": n_dupes,
                      "kinds": dict(Counter(v.split(":")[0] for v in kinds.values())), "transient_failure_rate": 0.15},
           "with_retry_and_idempotency": run(stream, kinds, redrive=True),
           "no_retry": run(stream, kinds, max_attempts=1),
           "retry_no_idempotency": run(stream, kinds, idempotent=False)}
    (ROOT / "results" / "simulation.json").write_text(json.dumps(out, indent=2))
    for k, v in out.items():
        if k == "stream": print("stream:", v); continue
        print(f"\n[{k}]")
        for kk in ("delivered", "routed_to_approval", "duplicates_suppressed", "dead_lettered", "dlq_by_reason", "retries",
                   "delivery_rate_of_deliverable_pct", "transient_loss_pct", "target_duplicate_deliveries",
                   "bad_messages_classified_correctly", "redrive", "attempts_histogram"):
            if kk in v: print(f"  {kk}: {v[kk]}")


if __name__ == "__main__":
    main()
