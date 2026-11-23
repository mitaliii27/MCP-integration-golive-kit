from pathlib import Path

import pytest

from integration.adapters import MockTarget
from integration.engine import MISSING, Engine, FlowDef, RetryPolicy, TransientError, apply_mapping, resolve

FLOWS = Path(__file__).resolve().parents[1] / "integration" / "flows"
ORDER = {"order_id": "A1", "customer": {"id": "c42"}, "total": 120, "lines": [{"sku": "m1", "qty": "3"}]}


def make(target=None, **kw):
    t = target or MockTarget("SalesOrder")
    return Engine(FlowDef.from_yaml(FLOWS / "orders_to_s4.yaml"), {"s4_orders": t}, **kw), t


class FailNTimes:
    def __init__(self, n, exc=TransientError("503")):
        self.n, self.exc, self.calls, self.received = n, exc, 0, []
    def send(self, payload, corr):
        self.calls += 1
        if self.calls <= self.n:
            raise self.exc
        self.received.append(payload)


def test_path_resolution():
    d = {"a": {"b": 1}, "items": [{"sku": "x"}]}
    assert resolve(d, "$.a.b") == 1 and resolve(d, "$.items[*]") == [{"sku": "x"}]
    assert resolve(d, "$.a.z") is MISSING and resolve(d, "$.a.b.c") is MISSING


def test_mapping_features():
    src = {"id": "a", "n": "5", "items": [{"s": "x"}, {"s": "y"}]}
    spec = {"K": "$.id", "C": {"const": 7}, "D": {"path": "$.nope", "default": "dflt"}, "N": {"path": "$.n", "transform": "int"},
            "Nested": {"Inner": {"path": "$.id", "transform": "upper"}}, "L": {"foreach": "$.items", "as": {"S": "$.s"}}}
    assert apply_mapping(spec, src) == {"K": "a", "C": 7, "D": "dflt", "N": 5, "Nested": {"Inner": "A"}, "L": [{"S": "x"}, {"S": "y"}]}


def test_happy_path_maps_and_delivers():
    e, t = make()
    o = e.process(ORDER)
    assert o.status == "delivered" and o.attempts == 1
    assert t.received[0] == {"SalesOrder": "A1", "SoldToParty": "C42", "Currency": "EUR", "TotalNetAmount": 120.0,
                             "Items": [{"Material": "M1", "Quantity": 3}]}


@pytest.mark.parametrize("bad,stage,fragment", [
    ({**ORDER, "customer": {}}, "validate", "customer.id"),
    ({**ORDER, "lines": []}, "validate", "$.lines"),
    ({**ORDER, "order_id": 123}, "validate", "must be string"),
    ({**ORDER, "total": -1}, "validate", "rule failed"),
    ({**ORDER, "lines": [{"sku": "m", "qty": "abc"}]}, "map", "transform int failed"),
    ({**ORDER, "lines": [{"qty": 1}]}, "map", "missing"),
])
def test_bad_messages_dead_letter_at_the_right_stage(bad, stage, fragment):
    e, t = make()
    o = e.process(bad)
    assert o.status == "dead_lettered" and o.stage == stage and fragment in o.reason and t.received == []
    assert e.dlq[0].payload == bad                      # original payload preserved for re-drive


def test_high_value_orders_route_to_approval_queue_not_target():
    e, t = make()
    o = e.process({**ORDER, "order_id": "BIG", "total": 25000})
    assert o.status == "routed" and o.destination == "approval_queue" and t.received == []
    assert e.queues["approval_queue"][0]["SalesOrder"] == "BIG"


def test_transient_failures_are_retried_with_exponential_backoff():
    slept = []
    e, t = make(FailNTimes(2), sleep=slept.append)
    o = e.process(ORDER)
    assert o.status == "delivered" and o.attempts == 3 and e.stats["retries"] == 2
    assert slept == [0.5, 1.0] and e.virtual_wait_s == 1.5


def test_retries_exhausted_goes_to_dlq_and_is_not_marked_processed():
    e, t = make(FailNTimes(99))
    o = e.process(ORDER)
    assert o.status == "dead_lettered" and o.reason == "retries_exhausted" and o.attempts == 4 and t.calls == 4
    assert "A1" not in e.processed


def test_permanent_errors_are_not_retried():
    from integration.engine import PermanentError
    e, t = make(FailNTimes(99, PermanentError("unknown sold-to party")))
    o = e.process(ORDER)
    assert o.status == "dead_lettered" and o.reason.startswith("permanent:") and t.calls == 1 and e.stats["retries"] == 0


def test_backoff_is_capped():
    rp = RetryPolicy(max_attempts=10, backoff_s=1, factor=10, max_backoff_s=5)
    assert [rp.delay(i) for i in (1, 2, 3)] == [1, 5, 5]


def test_idempotency_suppresses_duplicates_and_removing_it_would_double_deliver():
    e, t = make()
    assert e.process(ORDER).status == "delivered" and e.process(ORDER).status == "duplicate"
    assert t.duplicate_deliveries == 0 and len(t.received) == 1
    e2, t2 = make(idempotent=False)
    e2.process(ORDER); e2.process(ORDER)
    assert t2.duplicate_deliveries == 1                  # the failure mode idempotency prevents


def test_redrive_after_target_recovers_preserves_correlation_id():
    flaky = FailNTimes(4)                                # fails all 4 attempts of the first message, then healthy
    e, t = make(flaky)
    first = e.process(ORDER, correlation_id="corr-fixed")
    assert first.status == "dead_lettered" and len(e.dlq) == 1
    out = e.redrive()
    assert [o.status for o in out] == ["delivered"] and out[0].correlation_id == "corr-fixed" and e.dlq == []
    assert len(flaky.received) == 1


def test_redrive_filter_only_touches_selected_letters():
    e, _ = make()
    e.process({"order_id": "X", "lines": []}); e.process({**ORDER, "lines": [{"sku": "m", "qty": "z"}]})
    out = e.redrive(only=lambda d: d.stage == "map")
    assert len(out) == 1 and len(e.dlq) == 2             # map-stage letter re-failed and returned to DLQ; validate letter untouched


def test_trail_carries_one_correlation_id_through_every_stage():
    e, _ = make(FailNTimes(1))
    o = e.process(ORDER)
    events = [x for x in e.trail if x["corr"] == o.correlation_id]
    assert [x["event"] for x in events] == ["accepted", "decided", "transient_failure", "ok"]
    assert [x["stage"] for x in events] == ["receive", "route", "deliver", "deliver"]


def test_second_flow_is_pure_configuration():
    flow = FlowDef.from_yaml(FLOWS / "supplier_sync.yaml")
    t = MockTarget("Supplier")
    e = Engine(flow, {"s4_suppliers": t})
    assert flow.retry.max_attempts == 3
    assert e.process({"supplier_id": "s9", "name": "Acme", "bank": {"iban": "de12"}}).status == "delivered"
    assert t.received[0] == {"Supplier": "S9", "SupplierName": "Acme", "BankAccount": "DE12", "Country": "DE"}
