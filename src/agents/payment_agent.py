"""
PaymentAgent — reconciles order payments against items + freight.

Input:  order_id, raw_items (from OrderProductAgent)
Output: {
    currency: "BRL",
    payment_ids: list[str],       # "<order_id>:<payment_sequential>"
    payment_types: list[str],
    item_total_brl: float | None,
    freight_total_brl: float | None,
    expected_total_brl: float | None,
    payment_total_brl: float,
    difference_brl: float | None,
    reconciled: bool | None,
}
"""
from __future__ import annotations

from src.agents.base_agent import BaseAgent


class PaymentAgent(BaseAgent):
    name = "PaymentAgent"

    def run(self, case_id: str, order_id: str, raw_items: list[dict]) -> dict:
        self.log(case_id, "start", {"order_id": order_id})

        payments = self.db.get_order_payments(order_id)

        # payment_ids as "<order_id>:<payment_sequential>"
        payment_ids = [
            f"{order_id}:{row['payment_sequential']}"
            for row in payments
        ][:5]

        # payment_types (unique, preserve order)
        seen_types: list[str] = []
        for row in payments:
            pt = row.get("payment_type")
            if pt and pt not in seen_types:
                seen_types.append(pt)
        payment_types = seen_types

        # payment_total = sum of payment_value rows
        payment_total = round(
            sum(float(row.get("payment_value", 0)) for row in payments), 2
        )

        # If no item rows, expected fields are null (per spec)
        if not raw_items:
            result = {
                "currency": "BRL",
                "payment_ids": payment_ids,
                "payment_types": payment_types,
                "item_total_brl": None,
                "freight_total_brl": None,
                "expected_total_brl": None,
                "payment_total_brl": payment_total,
                "difference_brl": None,
                "reconciled": None,
            }
        else:
            item_total = round(
                sum(float(row.get("price", 0)) for row in raw_items), 2
            )
            freight_total = round(
                sum(float(row.get("freight_value", 0)) for row in raw_items), 2
            )
            expected_total = round(item_total + freight_total, 2)
            difference = round(payment_total - expected_total, 2)
            reconciled = abs(difference) <= 0.10

            result = {
                "currency": "BRL",
                "payment_ids": payment_ids,
                "payment_types": payment_types,
                "item_total_brl": item_total,
                "freight_total_brl": freight_total,
                "expected_total_brl": expected_total,
                "payment_total_brl": payment_total,
                "difference_brl": difference,
                "reconciled": reconciled,
            }

        self.log(case_id, "done", {
            "payment_total": payment_total,
            "reconciled": result.get("reconciled"),
        })
        return result
