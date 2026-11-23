"""A small, config-driven integration-flow engine in the spirit of an integration-suite iFlow:
validate -> map -> route -> deliver, with retry/backoff, dead-letter queue + re-drive,
idempotent receive and a correlation-ID trail.

This is a Python stand-in written for the portfolio. It is NOT SAP Integration Suite and does not
use its runtime, adapters or flow format; it demonstrates the same integration patterns.
"""
import itertools
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import yaml

MISSING = object()


class TransientError(Exception):
    """Target temporarily unavailable (HTTP 503/timeout style) - safe to retry."""


class PermanentError(Exception):
    """Target rejected the message (HTTP 4xx style) - retrying cannot help."""


class StepFailed(Exception):
    def __init__(self, stage: str, reason: str):
        super().__init__(f"{stage}: {reason}")
        self.stage, self.reason = stage, reason


# ------------------------------------------------------------------ path + mapping helpers
def resolve(obj: Any, path: str) -> Any:
    """JSONPath-lite: '$.a.b', '$.items[*].sku'. Returns MISSING when absent."""
    assert path.startswith("$"), f"bad path {path!r}"
    cur = obj
    for part in [p for p in path[1:].split(".") if p]:
        if part.endswith("[*]"):
            cur = cur.get(part[:-3], MISSING) if isinstance(cur, dict) else MISSING
            if not isinstance(cur, list):
                return MISSING
            return cur
        if not isinstance(cur, dict) or part not in cur:
            return MISSING
        cur = cur[part]
    return cur


_TRANSFORMS: dict[str, Callable[[Any], Any]] = {"upper": lambda v: str(v).upper(), "lower": lambda v: str(v).lower(),
                                                "int": int, "float": float, "str": str}
_OPS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
_TYPES = {"string": str, "list": list, "number": (int, float), "object": dict}


def apply_mapping(spec: Any, src: Any) -> Any:
    if isinstance(spec, str):
        v = resolve(src, spec) if spec.startswith("$") else spec
        if v is MISSING:
            raise StepFailed("map", f"path {spec} missing")
        return v
    if isinstance(spec, dict):
        if "foreach" in spec:
            items = resolve(src, spec["foreach"])
            if items is MISSING or not isinstance(items, list):
                raise StepFailed("map", f"foreach path {spec['foreach']} is not a list")
            return [apply_mapping(spec["as"], item) for item in items]
        if "const" in spec:
            return spec["const"]
        if "path" in spec:
            v = resolve(src, spec["path"])
            if v is MISSING:
                if "default" in spec:
                    return spec["default"]
                raise StepFailed("map", f"path {spec['path']} missing")
            try:
                return _TRANSFORMS[spec["transform"]](v) if "transform" in spec else v
            except (ValueError, TypeError) as exc:
                raise StepFailed("map", f"transform {spec['transform']} failed on {v!r}: {exc}")
        return {k: apply_mapping(s, src) for k, s in spec.items()}
    return spec


# ------------------------------------------------------------------------------ definitions
@dataclass
class RetryPolicy:
    max_attempts: int = 4
    backoff_s: float = 0.5
    factor: float = 2.0
    max_backoff_s: float = 8.0

    def delay(self, attempt: int) -> float:  # attempt = number of the attempt that just failed (1-based)
        return min(self.backoff_s * self.factor ** (attempt - 1), self.max_backoff_s)


@dataclass
class FlowDef:
    name: str
    steps: list[dict]
    idempotency_key: str
    retry: RetryPolicy = field(default_factory=RetryPolicy)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "FlowDef":
        d = yaml.safe_load(Path(path).read_text())
        return cls(d["name"], d["steps"], d["idempotency_key"], RetryPolicy(**d.get("retry", {})))


class Target(Protocol):
    def send(self, payload: dict, correlation_id: str) -> None: ...


@dataclass
class DeadLetter:
    correlation_id: str
    stage: str
    reason: str
    attempts: int
    payload: dict


@dataclass
class Outcome:
    status: str                # delivered | routed | duplicate | dead_lettered
    correlation_id: str
    attempts: int = 0
    stage: str = ""
    reason: str = ""
    destination: str = ""


class Engine:
    def __init__(self, flow: FlowDef, targets: dict[str, Target], idempotent: bool = True,
                 sleep: Callable[[float], None] | None = None):
        self.flow, self.targets, self.idempotent = flow, targets, idempotent
        self.sleep = sleep or (lambda s: None)
        self.processed: set[str] = set()
        self.queues: dict[str, list[dict]] = {}
        self.dlq: list[DeadLetter] = []
        self.trail: list[dict] = []
        self.stats: Counter = Counter()
        self.attempt_histogram: Counter = Counter()
        self.virtual_wait_s = 0.0
        self._ids = itertools.count(1)

    def _log(self, corr: str, stage: str, event: str, **extra) -> None:
        self.trail.append({"corr": corr, "stage": stage, "event": event, **extra})

    def process(self, payload: dict, correlation_id: str | None = None) -> Outcome:
        corr = correlation_id or f"corr-{next(self._ids):06d}"
        key = resolve(payload, self.flow.idempotency_key)
        key = None if key is MISSING else str(key)
        if self.idempotent and key is not None and key in self.processed:
            self.stats["duplicate"] += 1
            self._log(corr, "receive", "duplicate_suppressed", key=key)
            return Outcome("duplicate", corr)
        self._log(corr, "receive", "accepted", key=key)
        current, destination, attempts = payload, "deliver", 0
        try:
            for step in self.flow.steps:
                t = step["type"]
                if t == "validate":
                    self._validate(step, current)
                elif t == "map":
                    current = apply_mapping(step["mapping"], current)
                elif t == "route":
                    destination = self._route(step, current)
                    self._log(corr, "route", "decided", destination=destination)
                    if destination != "deliver":
                        self.queues.setdefault(destination, []).append(current)
                        self._finish(key); self.stats["routed"] += 1
                        return Outcome("routed", corr, destination=destination)
                elif t == "deliver":
                    attempts = self._deliver(self.targets[step["target"]], current, corr)
            self._finish(key); self.stats["delivered"] += 1; self.attempt_histogram[attempts] += 1
            return Outcome("delivered", corr, attempts=attempts)
        except StepFailed as exc:
            return self._dead_letter(corr, payload, exc.stage, exc.reason, getattr(exc, "attempts", attempts))

    # ---------------------------------------------------------------------------- steps
    def _finish(self, key: str | None) -> None:
        if key is not None:
            self.processed.add(key)

    @staticmethod
    def _validate(step: dict, p: dict) -> None:
        for path in step.get("required", []):
            v = resolve(p, path)
            if v is MISSING or v is None or v == "" or v == []:
                raise StepFailed("validate", f"required {path} missing/empty")
        for path, tname in step.get("types", {}).items():
            v = resolve(p, path)
            if v is not MISSING and (isinstance(v, bool) or not isinstance(v, _TYPES[tname])):
                raise StepFailed("validate", f"{path} must be {tname}")
        for rule in step.get("rules", []):
            v = resolve(p, rule["path"])
            if v is not MISSING and not _OPS[rule["op"]](v, rule["value"]):
                raise StepFailed("validate", f"rule failed: {rule['path']} {rule['op']} {rule['value']}")

    @staticmethod
    def _route(step: dict, p: dict) -> str:
        for rule in step.get("rules", []):
            w = rule["when"]; v = resolve(p, w["path"])
            if v is not MISSING and _OPS[w["op"]](v, w["value"]):
                return rule["to"]
        return step.get("default", "deliver")

    def _deliver(self, target: Target, payload: dict, corr: str) -> int:
        rp = self.flow.retry
        for attempt in range(1, rp.max_attempts + 1):
            try:
                target.send(payload, corr)
                self._log(corr, "deliver", "ok", attempt=attempt)
                return attempt
            except TransientError as exc:
                self._log(corr, "deliver", "transient_failure", attempt=attempt, error=str(exc))
                if attempt == rp.max_attempts:
                    err = StepFailed("deliver", "retries_exhausted"); err.attempts = attempt; raise err
                self.stats["retries"] += 1
                d = rp.delay(attempt); self.virtual_wait_s += d; self.sleep(d)
            except PermanentError as exc:
                err = StepFailed("deliver", f"permanent: {exc}"); err.attempts = attempt; raise err
        raise AssertionError("unreachable")

    def _dead_letter(self, corr: str, payload: dict, stage: str, reason: str, attempts: int) -> Outcome:
        self.dlq.append(DeadLetter(corr, stage, reason, attempts, payload))
        self.stats["dead_lettered"] += 1
        self._log(corr, stage, "dead_lettered", reason=reason)
        return Outcome("dead_lettered", corr, attempts=attempts, stage=stage, reason=reason)

    # --------------------------------------------------------------------------- re-drive
    def redrive(self, only: Callable[[DeadLetter], bool] | None = None) -> list[Outcome]:
        """Re-process dead letters (e.g. after the target recovered or a mapping bug was fixed)."""
        pending = [d for d in self.dlq if only is None or only(d)]
        self.dlq = [d for d in self.dlq if d not in pending]
        return [self.process(d.payload, correlation_id=d.correlation_id) for d in pending]
