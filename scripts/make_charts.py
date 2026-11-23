"""Render docs/img/simulation_summary.png from results/simulation.json (run `make sim` first)."""
import json, pathlib
from collections import Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = pathlib.Path(__file__).resolve().parents[1]
r = json.loads((root / "results/simulation.json").read_text())
A, B, C = r["with_retry_and_idempotency"], r["no_retry"], r["retry_no_idempotency"]
fig, ax = plt.subplots(1, 4, figsize=(17, 4))
g, red, gray = "#2f7d6d", "#b5453f", "#9a9a9a"

v = [B["delivery_rate_of_deliverable_pct"], A["delivery_rate_of_deliverable_pct"]]
bars = ax[0].bar(["no retry\n(1 attempt)", "retry\n(4 attempts, backoff)"], v, color=[gray, g])
for b, x in zip(bars, v): ax[0].text(b.get_x() + b.get_width() / 2, x + 1.5, f"{x:.2f}%", ha="center", fontweight="bold")
ax[0].set_ylim(0, 112); ax[0].set_title(f"Deliverable orders delivered\n({int(r['stream']['transient_failure_rate']*100)}% transient failure per attempt)", fontsize=10)

v = [A["target_duplicate_deliveries"], C["target_duplicate_deliveries"]]
bars = ax[1].bar(["idempotent\nreceiver", "no idempotency"], v, color=[g, red])
for b, x in zip(bars, v): ax[1].text(b.get_x() + b.get_width() / 2, x + 4, str(x), ha="center", fontweight="bold")
ax[1].set_ylim(0, max(v) * 1.2 + 1); ax[1].set_title(f"Duplicate deliveries reaching the target\n({r['stream']['duplicate_resends']} duplicate re-sends injected)", fontsize=10)

h = A["attempts_histogram"]
ax[2].bar([f"{k} attempt{'s' if k != '1' else ''}" for k in h], list(h.values()), color=g)
for i, x in enumerate(h.values()): ax[2].text(i, x + 40, str(x), ha="center", fontsize=9)
ax[2].set_title("Attempts needed per delivered message\n(retry scenario)", fontsize=10)

buckets = Counter()
for k, n in A["dlq_by_reason"].items():
    stage = k.split("/")[0]
    buckets["retries exhausted" if "retries_exhausted" in k else ("permanent reject" if "permanent" in k else f"{stage} failure")] += n
items = sorted(buckets.items(), key=lambda x: x[1])
ax[3].barh([k for k, _ in items], [n for _, n in items], color=["#c98a2b" if "exhausted" in k else "#7a5fb5" for k, _ in items])
for i, (_, n) in enumerate(items): ax[3].text(n + 1, i, str(n), va="center", fontsize=9)
ax[3].set_title("Dead-letter queue contents (retry scenario)\nbad data is parked, not retried forever", fontsize=10)
for a in ax: a.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
out = root / "docs/img/simulation_summary.png"; out.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches="tight"); print("wrote", out)
