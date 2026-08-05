"""
CustomerAgent — identifies customer identity and purchase history.

Input:  case dict (case_id, claimed_order_id)
Output: {
    customer_unique_id: str,
    related_order_ids: list[str]   # up to 5, excludes current order
}
"""
from __future__ import annotations

from src.agents.base_agent import BaseAgent


class CustomerAgent(BaseAgent):
    name = "CustomerAgent"

    def run(self, case_id: str, order_id: str) -> dict:
        self.log(case_id, "start", {"order_id": order_id})

        order = self.db.get_order(order_id)
        if order is None:
            self.log(case_id, "error", {"reason": "order_not_found"})
            return {"customer_unique_id": None, "related_order_ids": []}

        customer_id = order.get("customer_id")
        customer = self.db.get_customer(customer_id) if customer_id else None

        if customer is None:
            self.log(case_id, "error", {"reason": "customer_not_found"})
            return {"customer_unique_id": None, "related_order_ids": []}

        customer_unique_id: str = customer["customer_unique_id"]

        # Find all customer_ids sharing this unique_id
        all_customer_rows = self.db.get_customer_by_unique_id(customer_unique_id)
        all_customer_ids = [r["customer_id"] for r in all_customer_rows]

        # All orders for this unique customer
        all_order_ids = self.db.get_orders_by_customer_ids(all_customer_ids)

        # Exclude the current order; keep up to 5
        related = [oid for oid in all_order_ids if oid != order_id][:5]

        result = {
            "customer_unique_id": customer_unique_id,
            "related_order_ids": related,
        }
        self.log(case_id, "done", {
            "customer_unique_id": customer_unique_id,
            "related_count": len(related),
        })
        return result
