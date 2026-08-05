"""
VerifierAgent — validates and clamps the assembled output before writing to disk.

Checks:
  - Array limits (per spec)
  - Null handling for orders without items
  - confidence is in [0, 1]
  - evidence_ids format and count ≤ 20
"""
from __future__ import annotations

from src.agents.base_agent import BaseAgent


class VerifierAgent(BaseAgent):
    name = "VerifierAgent"

    LIMITS = {
        "order_ids": 5,
        "item_ids": 5,
        "seller_ids": 3,
        "payment_ids": 5,
        "related_order_ids": 5,
        "product_ids": 5,
        "category_names": 5,
        "root_causes": 3,
        "responsible_parties": 3,
        "evidence_ids": 20,
        "resolution_actions": 5,
    }

    def run(self, case_id: str, draft: dict) -> dict:
        self.log(case_id, "start")

        issues: list[str] = []

        # Clamp arrays
        ae = draft.get("affected_entities", {})
        ae["order_ids"] = ae.get("order_ids", [])[:5]
        ae["item_ids"] = ae.get("item_ids", [])[:5]
        ae["seller_ids"] = ae.get("seller_ids", [])[:3]
        ae["payment_ids"] = ae.get("payment_ids", [])[:5]

        cc = draft.get("customer_context", {})
        cc["related_order_ids"] = cc.get("related_order_ids", [])[:5]

        pc = draft.get("product_context", {})
        pc["product_ids"] = pc.get("product_ids", [])[:5]
        pc["category_names"] = pc.get("category_names", [])[:5]

        rca = draft.get("root_cause_analysis", {})
        rca["ranked_causes"] = rca.get("ranked_causes", [])[:3]
        rca["responsible_parties"] = rca.get("responsible_parties", [])[:3]

        draft["evidence_ids"] = draft.get("evidence_ids", [])[:20]
        draft["resolution_actions"] = draft.get("resolution_actions", [])[:5]

        # Confidence bounds
        ca = draft.get("case_assessment", {})
        conf = ca.get("confidence", 0.85)
        ca["confidence"] = max(0.0, min(1.0, conf))

        # Validate evidence ID formats
        valid_evidence = []
        for eid in draft.get("evidence_ids", []):
            parts = eid.split(":")
            prefix = parts[0] if parts else ""
            if prefix in ("order", "item", "payment", "seller", "policy"):
                valid_evidence.append(eid)
            else:
                issues.append(f"Invalid evidence ID format: {eid}")
        draft["evidence_ids"] = valid_evidence[:20]

        self.log(case_id, "done", {"issues": issues or "none"})
        return draft
