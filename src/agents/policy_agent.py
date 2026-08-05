"""
PolicyAgent — applies EC_POLICY_V2 to determine:
  - primary_issue, secondary_issues, case_status
  - responsible_parties, root_cause_analysis
  - financial_resolution, resolution_actions

Priority order (from spec):
  1. canceled_order_paid
  2. unavailable_order_paid
  3. late_delivery_seller
  4. late_delivery_logistics
  5. valid_split_payment
  6. unsupported_late_claim

Secondary issues (in spec order):
  1. multi_item_order   (≥2 items)
  2. multi_seller_order (≥2 sellers)
  3. split_payment      (≥2 payment rows)
  4. repeat_customer    (has related orders)
  5. multiple_categories (≥2 categories)

Supplemental actions (appended after primary action):
  - review_seller_handoff  (if late_delivery_seller)
  - review_carrier_delay   (if late_delivery_logistics)
  - verify_refund_completion (if refund > 0)
  - coordinate_multi_seller_case (if multi_seller_order)
  - verify_payment_allocation (if split_payment AND NOT valid_split_payment primary)
"""
from __future__ import annotations

from src.agents.base_agent import BaseAgent


class PolicyAgent(BaseAgent):
    name = "PolicyAgent"

    def run(
        self,
        case_id: str,
        order_id: str,
        order_status: str | None,
        raw_items: list[dict],
        payments_data: dict,
        delivery_data: dict,
        customer_data: dict,
        order_product_data: dict,
    ) -> dict:
        self.log(case_id, "start", {"order_id": order_id})

        payment_total = payments_data.get("payment_total_brl", 0) or 0
        freight_total = payments_data.get("freight_total_brl") or 0
        reconciled = payments_data.get("reconciled")
        num_payments = len(payments_data.get("payment_ids", []))
        num_items = len(raw_items)
        num_sellers = len(order_product_data.get("seller_ids", []))
        num_categories = len(order_product_data.get("category_names", []))
        has_related_orders = len(customer_data.get("related_order_ids", [])) > 0

        is_late = delivery_data.get("is_late_delivery")
        any_seller_late = delivery_data.get("any_seller_late", False)
        late_seller_ids = delivery_data.get("late_handoff_seller_ids", [])

        # ------------------------------------------------------------------ #
        # PRIMARY ISSUE (evaluated in priority order)
        # ------------------------------------------------------------------ #
        primary_issue: str
        responsible_parties: list[dict]
        refund_brl: float
        primary_action: str
        root_cause_code: str

        if order_status == "canceled" and payment_total > 0:
            primary_issue = "canceled_order_paid"
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            refund_brl = round(payment_total, 2)
            primary_action = "issue_full_refund"
            root_cause_code = "ORDER_CANCELED_AFTER_PAYMENT"

        elif order_status == "unavailable" and payment_total > 0:
            primary_issue = "unavailable_order_paid"
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            refund_brl = round(payment_total, 2)
            primary_action = "issue_full_refund"
            root_cause_code = "ORDER_UNAVAILABLE_AFTER_PAYMENT"

        elif is_late and any_seller_late:
            primary_issue = "late_delivery_seller"
            responsible_parties = [
                {"party_type": "seller", "party_id": sid}
                for sid in late_seller_ids[:3]
            ]
            refund_brl = round(freight_total, 2)
            primary_action = "refund_freight"
            root_cause_code = "SELLER_HANDOFF_AFTER_LIMIT"

        elif is_late and not any_seller_late:
            primary_issue = "late_delivery_logistics"
            responsible_parties = [
                {"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}
            ]
            refund_brl = round(freight_total, 2)
            primary_action = "refund_freight"
            root_cause_code = "CARRIER_DELIVERED_AFTER_ESTIMATE"

        elif num_payments >= 2 and reconciled is True:
            primary_issue = "valid_split_payment"
            responsible_parties = []
            refund_brl = 0.0
            primary_action = "explain_valid_split_payment"
            root_cause_code = "MULTIPLE_PAYMENTS_RECONCILED"

        else:
            primary_issue = "unsupported_late_claim"
            responsible_parties = []
            refund_brl = 0.0
            primary_action = "reject_late_refund"
            root_cause_code = "DELIVERY_WITHIN_ESTIMATE"

        # ------------------------------------------------------------------ #
        # SECONDARY ISSUES (in spec order)
        # ------------------------------------------------------------------ #
        secondary_issues: list[str] = []
        if num_items >= 2:
            secondary_issues.append("multi_item_order")
        if num_sellers >= 2:
            secondary_issues.append("multi_seller_order")
        if num_payments >= 2:
            secondary_issues.append("split_payment")
        if has_related_orders:
            secondary_issues.append("repeat_customer")
        if num_categories >= 2:
            secondary_issues.append("multiple_categories")

        # ------------------------------------------------------------------ #
        # CASE STATUS
        # ------------------------------------------------------------------ #
        case_status = "action_required" if refund_brl > 0 else "no_action"

        # ------------------------------------------------------------------ #
        # RESOLUTION ACTIONS (primary + supplemental in spec order)
        # Per README example: late_delivery_seller →
        #   [refund_freight, review_seller_handoff, verify_payment_allocation]
        #   (no verify_refund_completion for freight refund cases)
        # verify_refund_completion only for issue_full_refund (canceled/unavailable)
        # ------------------------------------------------------------------ #
        actions: list[str] = [primary_action]
        if primary_issue == "late_delivery_seller":
            actions.append("review_seller_handoff")
        elif primary_issue == "late_delivery_logistics":
            actions.append("review_carrier_delay")
        if primary_action == "issue_full_refund":
            actions.append("verify_refund_completion")
        if "multi_seller_order" in secondary_issues:
            actions.append("coordinate_multi_seller_case")
        if "split_payment" in secondary_issues and primary_issue != "valid_split_payment":
            actions.append("verify_payment_allocation")
        actions = actions[:5]

        result = {
            "primary_issue": primary_issue,
            "secondary_issues": secondary_issues,
            "case_status": case_status,
            "responsible_parties": responsible_parties,
            "root_cause_code": root_cause_code,
            "refund_brl": refund_brl,
            "resolution_actions": actions,
        }
        self.log(case_id, "done", {
            "primary_issue": primary_issue,
            "case_status": case_status,
            "refund_brl": refund_brl,
        })
        return result
