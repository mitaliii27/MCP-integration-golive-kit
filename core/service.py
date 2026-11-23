"""Business core shared by the MCP server: in-memory stand-in for an S/4-style procurement backend.

Simplified entities/fields, NOT SAP's real API schemas. Writes are idempotent on `request_id`
because agents and MCP clients retry; a retried call must not create a second requisition.
"""
from dataclasses import dataclass, field

from .data import seed_data


@dataclass
class Policy:
    approval_threshold_eur: float = 5000.0
    max_quantity: float = 10000
    allowed_plants: tuple[str, ...] = ("1010", "1020")


class BusinessError(ValueError):
    """Invalid input (unknown material, bad quantity...). Surfaces as an MCP tool error."""


@dataclass
class ProcurementService:
    policy: Policy = field(default_factory=Policy)
    seed: int = 7

    def __post_init__(self):
        self.materials, self.stock, self.suppliers, self.info = seed_data(self.seed)
        self.requisitions: list[dict] = []
        self._by_request_id: dict[str, dict] = {}

    # ------------------------------------------------------------------ reads
    def search_materials(self, query: str) -> list[dict]:
        q = query.strip().lower()
        if len(q) < 2:
            raise BusinessError("query must be at least 2 characters")
        return [m for m in self.materials if q in m["MaterialDescription"].lower()][:5]

    def check_stock(self, material: str, plant: str | None = None) -> list[dict]:
        rows = [dict(r, BelowReorderPoint=r["UnrestrictedStock"] < r["ReorderPoint"])
                for r in self.stock if r["Material"] == material and (plant is None or r["Plant"] == plant)]
        if not rows:
            raise BusinessError(f"no stock data for material {material!r}" + (f" at plant {plant!r}" if plant else ""))
        return rows

    def find_suppliers(self, material: str) -> list[dict]:
        names = {s["Supplier"]: s["SupplierName"] for s in self.suppliers}
        rows = sorted((dict(i, SupplierName=names[i["Supplier"]]) for i in self.info if i["Material"] == material),
                      key=lambda r: r["NetPrice"])
        if not rows:
            raise BusinessError(f"no suppliers found for material {material!r}")
        return rows

    def get_requisition(self, pr_number: str) -> dict:
        for pr in self.requisitions:
            if pr["PurchaseRequisition"] == pr_number:
                return pr
        raise BusinessError(f"requisition {pr_number!r} not found")

    # ----------------------------------------------------------------- writes
    def create_purchase_requisition(self, material: str, quantity: float, supplier: str, plant: str,
                                    justification: str = "", request_id: str | None = None) -> dict:
        if request_id and request_id in self._by_request_id:
            return {"status": "created", "idempotent_replay": True, "purchase_requisition": self._by_request_id[request_id]}
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity <= 0:
            raise BusinessError("quantity must be a positive number")
        p = self.policy
        if quantity > p.max_quantity:
            return {"status": "denied", "reason": f"quantity {quantity:,.0f} exceeds maximum {p.max_quantity:,.0f}"}
        if plant not in p.allowed_plants:
            return {"status": "denied", "reason": f"plant {plant!r} is not permitted"}
        match = [i for i in self.info if i["Material"] == material and i["Supplier"] == supplier]
        if not match:
            raise BusinessError(f"supplier {supplier!r} does not supply material {material!r}")
        value = round(quantity * match[0]["NetPrice"], 2)
        if value > p.approval_threshold_eur:
            return {"status": "approval_required", "estimated_value_eur": value,
                    "reason": f"value EUR {value:,.2f} exceeds approval threshold EUR {p.approval_threshold_eur:,.2f}"}
        pr = {"PurchaseRequisition": f"PR-{100001 + len(self.requisitions)}", "Material": material, "Plant": plant,
              "Quantity": quantity, "Supplier": supplier, "NetPrice": match[0]["NetPrice"], "TotalValue": value,
              "Justification": justification, "Status": "CREATED"}
        self.requisitions.append(pr)
        if request_id:
            self._by_request_id[request_id] = pr
        return {"status": "created", "idempotent_replay": False, "purchase_requisition": pr}
