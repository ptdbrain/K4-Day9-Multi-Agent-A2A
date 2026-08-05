"""
CoordinatorAgent — orchestrates all specialist agents and assembles final output.

Flow:
  1. CustomerAgent    → customer identity + history
  2. OrderProductAgent → order, items, sellers, products, categories
  3. PaymentAgent     → payment reconciliation
  4. DeliveryAgent    → delivery + seller handoff
  5. PolicyAgent      → EC_POLICY_V2 rule engine
  6. [LLM call]       → confidence estimation (OpenRouter: meta-llama/llama-3.2-3b-instruct)
  7. Assemble output dict
  8. VerifierAgent    → validate + clamp arrays
  9. Write JSON to output/
"""
from __future__ import annotations

import os

from src.agents.base_agent import BaseAgent
from src.agents.customer_agent import CustomerAgent
from src.agents.delivery_agent import DeliveryAgent
from src.agents.order_product_agent import OrderProductAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.verifier_agent import VerifierAgent

# Model declared in source code per spec (must NOT go in .env)
# Using OpenRouter provider — qwen/qwen3.5-9b (9B params, ≤10B)
LLM_MODEL = "qwen/qwen3.5-9b"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class CoordinatorAgent(BaseAgent):
    name = "CoordinatorAgent"

    def __init__(self) -> None:
        super().__init__()
        self.customer_agent = CustomerAgent()
        self.order_product_agent = OrderProductAgent()
        self.payment_agent = PaymentAgent()
        self.delivery_agent = DeliveryAgent()
        self.policy_agent = PolicyAgent()
        self.verifier_agent = VerifierAgent()
        self._llm = None

    def _get_llm(self):
        """Lazy-init OpenRouter client (OpenAI-compatible API)."""
        if self._llm is not None:
            return self._llm
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
            if api_key:
                self._llm = OpenAI(
                    base_url=OPENROUTER_BASE_URL,
                    api_key=api_key,
                )
        except Exception:
            self._llm = None
        return self._llm

    def _estimate_confidence(
        self,
        case_id: str,
        primary_issue: str,
        delivery_data: dict,
        payment_data: dict,
        policy_data: dict,
    ) -> float:
        """
        Rule-based confidence scoring — deterministic, no API call.
        Scoring rationale:
          - Clear-cut issues (canceled/unavailable) get high base confidence.
          - Late delivery confidence scales with variance magnitude.
          - Penalties for missing timestamps or unreconciled payments.
        """
        base: float

        if primary_issue in ("canceled_order_paid", "unavailable_order_paid"):
            # Unambiguous: status field + payment total both confirm
            base = 0.98

        elif primary_issue == "late_delivery_seller":
            variance = delivery_data.get("delivery_variance_hours") or 0
            if variance >= 72:
                base = 0.95   # clearly very late
            elif variance >= 24:
                base = 0.92   # confidently late
            else:
                base = 0.87   # borderline late

        elif primary_issue == "late_delivery_logistics":
            variance = delivery_data.get("delivery_variance_hours") or 0
            base = 0.90 if variance >= 24 else 0.85

        elif primary_issue == "valid_split_payment":
            # Multiple payments, reconciled within tolerance
            base = 0.93

        else:  # unsupported_late_claim
            variance = delivery_data.get("delivery_variance_hours") or 0
            # The more negative (earlier than estimated), the more confident
            base = 0.95 if variance <= -48 else 0.90 if variance <= 0 else 0.80

        # Penalties for data quality issues
        if delivery_data.get("delivered_at") is None:
            base -= 0.12
        if payment_data.get("reconciled") is False:
            base -= 0.08
        if payment_data.get("reconciled") is None:
            base -= 0.05

        conf = round(max(0.0, min(1.0, base)), 2)
        self.log(case_id, "confidence_scored", {"primary": primary_issue, "confidence": conf})
        return conf


    def _build_evidence_ids(
        self,
        order_id: str,
        raw_items: list[dict],
        payments_data: dict,
        policy_data: dict,
        responsible_seller_ids: list[str],
    ) -> list[str]:
        evidence: list[str] = []

        # order
        evidence.append(f"order:{order_id}")

        # items (up to 5)
        for item in raw_items[:5]:
            evidence.append(f"item:{order_id}:{item['order_item_id']}")

        # payments (up to 5)
        for pid in payments_data.get("payment_ids", [])[:5]:
            evidence.append(f"payment:{pid}")

        # responsible sellers
        for sid in responsible_seller_ids[:3]:
            evidence.append(f"seller:{sid}")

        # policy
        root_cause = policy_data.get("root_cause_code")
        if root_cause:
            evidence.append(f"policy:{root_cause}")

        return evidence[:20]

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def process_case(self, case: dict) -> dict:
        case_id: str = case["case_id"]
        order_id: str = case["customer_request"]["claimed_order_id"]

        self.log(case_id, "start", {"order_id": order_id})

        # ── 1. Customer ──────────────────────────────────────────────
        customer_data = self.customer_agent.run(case_id, order_id)

        # ── 2. Order & Product ──────────────────────────────────────
        order_product_data = self.order_product_agent.run(case_id, order_id)
        raw_items = order_product_data["raw_items"]
        order_status = order_product_data["order_status"]

        # ── 3. Payment ──────────────────────────────────────────────
        payments_data = self.payment_agent.run(case_id, order_id, raw_items)

        # ── 4. Delivery ─────────────────────────────────────────────
        delivery_data = self.delivery_agent.run(case_id, order_id, raw_items)

        # ── 5. Policy ───────────────────────────────────────────────
        policy_data = self.policy_agent.run(
            case_id=case_id,
            order_id=order_id,
            order_status=order_status,
            raw_items=raw_items,
            payments_data=payments_data,
            delivery_data=delivery_data,
            customer_data=customer_data,
            order_product_data=order_product_data,
        )

        # ── 6. Confidence (rule-based, instant) ──────────────────────
        confidence = self._estimate_confidence(
            case_id,
            policy_data["primary_issue"],
            delivery_data,
            payments_data,
            policy_data,
        )

        # ── 7. Build evidence IDs ───────────────────────────────────
        responsible_seller_ids = [
            p["party_id"]
            for p in policy_data["responsible_parties"]
            if p["party_type"] == "seller"
        ]
        evidence_ids = self._build_evidence_ids(
            order_id, raw_items, payments_data, policy_data, responsible_seller_ids
        )

        # ── 8. Assemble output ──────────────────────────────────────
        ranked_causes = [
            {"cause_code": policy_data["root_cause_code"], "rank": 1}
        ]

        draft = {
            "case_id": case_id,
            "case_assessment": {
                "primary_issue": policy_data["primary_issue"],
                "secondary_issues": policy_data["secondary_issues"],
                "case_status": policy_data["case_status"],
                "confidence": confidence,
            },
            "affected_entities": {
                "order_ids": [order_id],
                "item_ids": order_product_data["item_ids"],
                "seller_ids": order_product_data["seller_ids"],
                "payment_ids": payments_data["payment_ids"],
            },
            "customer_context": {
                "customer_unique_id": customer_data["customer_unique_id"],
                "related_order_ids": customer_data["related_order_ids"],
            },
            "product_context": {
                "product_ids": order_product_data["product_ids"],
                "category_names": order_product_data["category_names"],
            },
            "delivery_analysis": {
                "delivered_at": delivery_data["delivered_at"],
                "estimated_delivery_at": delivery_data["estimated_delivery_at"],
                "carrier_handoff_at": delivery_data["carrier_handoff_at"],
                "delivery_variance_hours": delivery_data["delivery_variance_hours"],
                "seller_handoff_analysis": delivery_data["seller_handoff_analysis"],
                "late_handoff_seller_ids": delivery_data["late_handoff_seller_ids"],
            },
            "payment_reconciliation": {
                "currency": "BRL",
                "item_total_brl": payments_data["item_total_brl"],
                "freight_total_brl": payments_data["freight_total_brl"],
                "expected_total_brl": payments_data["expected_total_brl"],
                "payment_total_brl": payments_data["payment_total_brl"],
                "difference_brl": payments_data["difference_brl"],
                "reconciled": payments_data["reconciled"],
                "payment_types": payments_data["payment_types"],
            },
            "root_cause_analysis": {
                "ranked_causes": ranked_causes,
                "responsible_parties": policy_data["responsible_parties"],
            },
            "evidence_ids": evidence_ids,
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": policy_data["refund_brl"],
            },
            "resolution_actions": policy_data["resolution_actions"],
        }

        # ── 9. Verify ───────────────────────────────────────────────
        output = self.verifier_agent.run(case_id, draft)

        self.log(case_id, "complete", {
            "primary_issue": policy_data["primary_issue"],
            "case_status": policy_data["case_status"],
        })
        return output
