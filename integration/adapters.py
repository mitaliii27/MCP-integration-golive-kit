"""Test/simulation targets with controllable failure injection (seeded, deterministic)."""
import random
from collections import Counter
from typing import Callable

from .engine import PermanentError, TransientError


class MockTarget:
    def __init__(self, key_field: str, transient_rate: float = 0.0, seed: int = 0,
                 reject: Callable[[dict], str | None] | None = None):
        self.key_field, self.transient_rate, self.rng, self.reject = key_field, transient_rate, random.Random(seed), reject
        self.received: list[dict] = []
        self.key_counts: Counter = Counter()
        self.send_calls = 0

    def send(self, payload: dict, correlation_id: str) -> None:
        self.send_calls += 1
        if self.rng.random() < self.transient_rate:
            raise TransientError("503 service unavailable (injected)")
        reason = self.reject(payload) if self.reject else None
        if reason:
            raise PermanentError(reason)
        self.received.append(payload)
        self.key_counts[payload[self.key_field]] += 1

    @property
    def duplicate_deliveries(self) -> int:
        return sum(c - 1 for c in self.key_counts.values() if c > 1)
