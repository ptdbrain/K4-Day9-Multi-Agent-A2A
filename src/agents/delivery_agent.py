"""
DeliveryAgent — computes delivery variance and seller handoff analysis.

Formulas (from EC_POLICY_V2):
  delivery_variance_hours = order_delivered_customer_date - order_estimated_delivery_date
  handoff_variance_hours  = order_delivered_carrier_date - min(shipping_limit_date) per seller

Input:  order_id, raw_items
Output: {
    delivered_at: str | None,
    estimated_delivery_at: str | None,
    carrier_handoff_at: str | None,
    delivery_variance_hours: float | None,
    seller_handoff_analysis: list[dict],
    late_handoff_seller_ids: list[str],
    is_late_delivery: bool | None,
    any_seller_late: bool,
}
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from src.agents.base_agent import BaseAgent

_FMT = "%Y-%m-%d %H:%M:%S"


def _fmt(ts) -> Optional[str]:
    """Convert pandas Timestamp or datetime to CSV format string.
    Handles NaT, NaN, None, and normal datetime values safely.
    """
    if ts is None:
        return None
    try:
        # pd.isnull() handles both float NaN and pd.NaT
        if pd.isnull(ts):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return ts.strftime(_FMT)
    except (AttributeError, ValueError):
        s = str(ts)
        return None if s in ("NaT", "nan", "None", "") else s


class DeliveryAgent(BaseAgent):
    name = "DeliveryAgent"

    def run(self, case_id: str, order_id: str, raw_items: list[dict]) -> dict:
        self.log(case_id, "start", {"order_id": order_id})

        order = self.db.get_order(order_id)
        if order is None:
            return self._null_result()

        delivered_ts = order.get("order_delivered_customer_date")
        estimated_ts = order.get("order_estimated_delivery_date")
        carrier_ts = order.get("order_delivered_carrier_date")

        delivered_at = _fmt(delivered_ts)
        estimated_at = _fmt(estimated_ts)
        carrier_handoff_at = _fmt(carrier_ts)

        # Delivery variance (hours)
        delivery_variance_hours: Optional[float] = None
        is_late_delivery: Optional[bool] = None
        if pd.notna(delivered_ts) and pd.notna(estimated_ts):
            delta = (delivered_ts - estimated_ts).total_seconds() / 3600
            delivery_variance_hours = round(delta, 2)
            is_late_delivery = delta > 0

        # Seller handoff analysis
        seller_handoff_analysis: list[dict] = []
        late_handoff_seller_ids: list[str] = []

        if raw_items and pd.notna(carrier_ts):
            # Group items by seller, find earliest shipping_limit_date per seller
            seller_limits: dict[str, pd.Timestamp] = {}
            for row in raw_items:
                sid = row.get("seller_id")
                sld = row.get("shipping_limit_date")
                if sid and pd.notna(sld):
                    if sid not in seller_limits or sld < seller_limits[sid]:
                        seller_limits[sid] = sld

            for sid, earliest_limit in seller_limits.items():
                variance_hours = round(
                    (carrier_ts - earliest_limit).total_seconds() / 3600, 2
                )
                late = variance_hours > 0
                seller_handoff_analysis.append({
                    "seller_id": sid,
                    "shipping_limit_at": _fmt(earliest_limit),
                    "handoff_variance_hours": variance_hours,
                    "late_handoff": late,
                })
                if late:
                    late_handoff_seller_ids.append(sid)

        any_seller_late = len(late_handoff_seller_ids) > 0

        result = {
            "delivered_at": delivered_at,
            "estimated_delivery_at": estimated_at,
            "carrier_handoff_at": carrier_handoff_at,
            "delivery_variance_hours": delivery_variance_hours,
            "seller_handoff_analysis": seller_handoff_analysis,
            "late_handoff_seller_ids": late_handoff_seller_ids,
            "is_late_delivery": is_late_delivery,
            "any_seller_late": any_seller_late,
        }
        self.log(case_id, "done", {
            "is_late_delivery": is_late_delivery,
            "delivery_variance_hours": delivery_variance_hours,
            "any_seller_late": any_seller_late,
        })
        return result

    def _null_result(self) -> dict:
        return {
            "delivered_at": None,
            "estimated_delivery_at": None,
            "carrier_handoff_at": None,
            "delivery_variance_hours": None,
            "seller_handoff_analysis": [],
            "late_handoff_seller_ids": [],
            "is_late_delivery": None,
            "any_seller_late": False,
        }
