import datetime
import math

# Các hàm helper để parse và so sánh date time
def parse_date(date_str):
    if not date_str or str(date_str) == 'nan' or str(date_str) == 'None':
        return None
    # Xử lý định dạng YYYY-MM-DD HH:MM:SS
    try:
        return datetime.datetime.strptime(str(date_str), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.datetime.strptime(str(date_str).split('.')[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

def format_date(dt):
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def clean_float(val):
    if val is None:
        return None
    val = round(float(val), 2)
    if val == 0.0:
        return 0.0
    return val

def get_variance_hours(dt1, dt2):
    if dt1 is None or dt2 is None:
        return None
    diff = dt1 - dt2
    val = diff.total_seconds() / 3600.0
    return clean_float(val)


class CustomerAgent:
    def __init__(self, db):
        self.db = db

    def process(self, order_id, customer_id):
        # Lấy customer info
        cust_info = self.db.get_customer_by_id(customer_id)
        if not cust_info:
            return {
                "customer_unique_id": None,
                "related_order_ids": [],
                "repeat_customer": False
            }
        
        cust_uniq_id = cust_info.get("customer_unique_id")
        
        # Lấy lịch sử order
        related_orders = self.db.get_customer_history(cust_uniq_id, order_id)
        # Giới hạn tối đa 5 related order
        related_orders_limited = related_orders[:5]
        
        return {
            "customer_unique_id": cust_uniq_id,
            "related_order_ids": related_orders_limited,
            "repeat_customer": len(related_orders) > 0
        }


class OrderProductAgent:
    def __init__(self, db):
        self.db = db

    def process(self, order_id):
        items = self.db.get_order_items(order_id)
        
        product_ids = []
        category_names = []
        seller_ids = []
        item_ids = []
        
        for item in items:
            p_id = item.get("product_id")
            s_id = item.get("seller_id")
            cat = item.get("product_category_name")
            item_seq = item.get("order_item_id")
            
            if p_id and p_id not in product_ids:
                product_ids.append(p_id)
            if s_id and s_id not in seller_ids:
                seller_ids.append(s_id)
            if cat and str(cat) != 'nan' and cat not in category_names:
                category_names.append(cat)
            
            if item_seq is not None and str(item_seq) != 'nan':
                item_ids.append(f"{order_id}:{int(item_seq)}")

        # Giới hạn
        product_ids_limited = product_ids[:5]
        category_names_limited = category_names[:5]
        seller_ids_limited = seller_ids[:3]
        item_ids_limited = item_ids[:5]
        
        # Check secondary issues
        multi_item_order = len(items) >= 2
        multi_seller_order = len(seller_ids) >= 2
        multiple_categories = len(category_names) >= 2

        return {
            "items_raw": items,
            "product_ids": product_ids_limited,
            "category_names": category_names_limited,
            "seller_ids": seller_ids_limited,
            "item_ids": item_ids_limited,
            "multi_item_order": multi_item_order,
            "multi_seller_order": multi_seller_order,
            "multiple_categories": multiple_categories
        }


class PaymentAgent:
    def __init__(self, db):
        self.db = db

    def process(self, order_id, items_raw):
        payments = self.db.get_order_payments(order_id)
        
        payment_ids = []
        payment_types = []
        payment_total_brl = 0.0
        
        for p in payments:
            seq = p.get("payment_sequential")
            p_type = p.get("payment_type")
            val = p.get("payment_value")
            
            if seq is not None and str(seq) != 'nan':
                payment_ids.append(f"{order_id}:{int(seq)}")
            if p_type and p_type not in payment_types:
                payment_types.append(p_type)
            if val is not None:
                payment_total_brl += float(val)

        payment_ids_limited = payment_ids[:5]
        split_payment = len(payments) >= 2

        if not items_raw:
            # Với order không có item row, expected_total_brl, difference_brl và reconciled phải là null
            return {
                "currency": "BRL",
                "item_total_brl": 0.0,
                "freight_total_brl": 0.0,
                "expected_total_brl": None,
                "payment_total_brl": clean_float(payment_total_brl),
                "difference_brl": None,
                "reconciled": None,
                "payment_ids": payment_ids_limited,
                "payment_types": payment_types,
                "split_payment": split_payment
            }

        item_total_brl = sum(float(item.get("price", 0)) for item in items_raw)
        freight_total_brl = sum(float(item.get("freight_value", 0)) for item in items_raw)
        expected_total_brl = item_total_brl + freight_total_brl
        
        difference_brl = payment_total_brl - expected_total_brl
        reconciled = abs(difference_brl) <= 0.10

        return {
            "currency": "BRL",
            "item_total_brl": clean_float(item_total_brl),
            "freight_total_brl": clean_float(freight_total_brl),
            "expected_total_brl": clean_float(expected_total_brl),
            "payment_total_brl": clean_float(payment_total_brl),
            "difference_brl": clean_float(difference_brl),
            "reconciled": reconciled,
            "payment_ids": payment_ids_limited,
            "payment_types": payment_types,
            "split_payment": split_payment
        }


class DeliveryAgent:
    def __init__(self, db):
        self.db = db

    def process(self, order_id, order_details, items_raw):
        delivered_at_str = order_details.get("order_delivered_customer_date")
        estimated_delivery_at_str = order_details.get("order_estimated_delivery_date")
        carrier_handoff_at_str = order_details.get("order_delivered_carrier_date")

        delivered_at = parse_date(delivered_at_str)
        estimated_delivery_at = parse_date(estimated_delivery_at_str)
        carrier_handoff_at = parse_date(carrier_handoff_at_str)

        delivery_variance_hours = get_variance_hours(delivered_at, estimated_delivery_at)

        # Phân tích seller handoff
        # Lấy shipping_limit_date sớm nhất cho từng seller
        seller_limits = {}
        for item in items_raw:
            s_id = item.get("seller_id")
            s_limit_str = item.get("shipping_limit_date")
            s_limit = parse_date(s_limit_str)
            if s_id and s_limit:
                if s_id not in seller_limits or s_limit < seller_limits[s_id]:
                    seller_limits[s_id] = s_limit

        seller_handoff_analysis = []
        late_handoff_seller_ids = []

        for s_id, s_limit in seller_limits.items():
            h_var = get_variance_hours(carrier_handoff_at, s_limit)
            late_handoff = False
            if h_var is not None and h_var > 0:
                late_handoff = True
                late_handoff_seller_ids.append(s_id)
            
            seller_handoff_analysis.append({
                "seller_id": s_id,
                "shipping_limit_at": format_date(s_limit),
                "handoff_variance_hours": h_var,
                "late_handoff": late_handoff
            })

        return {
            "delivered_at": format_date(delivered_at),
            "estimated_delivery_at": format_date(estimated_delivery_at),
            "carrier_handoff_at": format_date(carrier_handoff_at),
            "delivery_variance_hours": delivery_variance_hours,
            "seller_handoff_analysis": seller_handoff_analysis,
            "late_handoff_seller_ids": late_handoff_seller_ids
        }


class PolicyAgent:
    def process(self, order_id, order_details, cust_facts, order_facts, pay_facts, del_facts):
        order_status = order_details.get("order_status")
        payment_total_brl = pay_facts["payment_total_brl"]
        delivery_variance_hours = del_facts["delivery_variance_hours"]
        late_handoff_seller_ids = del_facts["late_handoff_seller_ids"]
        split_payment = pay_facts["split_payment"]
        reconciled = pay_facts["reconciled"]

        primary_issue = None
        responsible_parties = []
        recommended_refund_brl = 0.0
        primary_action = None
        root_cause_code = None

        # 1. canceled_order_paid
        if order_status == "canceled" and payment_total_brl > 0:
            primary_issue = "canceled_order_paid"
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            recommended_refund_brl = payment_total_brl
            primary_action = "issue_full_refund"
            root_cause_code = "ORDER_CANCELED_AFTER_PAYMENT"

        # 2. unavailable_order_paid
        elif order_status == "unavailable" and payment_total_brl > 0:
            primary_issue = "unavailable_order_paid"
            responsible_parties = [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}]
            recommended_refund_brl = payment_total_brl
            primary_action = "issue_full_refund"
            root_cause_code = "ORDER_UNAVAILABLE_AFTER_PAYMENT"

        # 3. late_delivery_seller
        elif delivery_variance_hours is not None and delivery_variance_hours > 0 and len(late_handoff_seller_ids) > 0:
            primary_issue = "late_delivery_seller"
            responsible_parties = [{"party_type": "seller", "party_id": s_id} for s_id in late_handoff_seller_ids[:3]]
            recommended_refund_brl = pay_facts["freight_total_brl"]
            primary_action = "refund_freight"
            root_cause_code = "SELLER_HANDOFF_AFTER_LIMIT"

        # 4. late_delivery_logistics
        elif delivery_variance_hours is not None and delivery_variance_hours > 0 and len(late_handoff_seller_ids) == 0:
            primary_issue = "late_delivery_logistics"
            responsible_parties = [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}]
            recommended_refund_brl = pay_facts["freight_total_brl"]
            primary_action = "refund_freight"
            root_cause_code = "CARRIER_DELIVERED_AFTER_ESTIMATE"

        # 5. valid_split_payment
        elif split_payment and reconciled:
            primary_issue = "valid_split_payment"
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = "explain_valid_split_payment"
            root_cause_code = "MULTIPLE_PAYMENTS_RECONCILED"

        # 6. unsupported_late_claim
        else:
            primary_issue = "unsupported_late_claim"
            responsible_parties = []
            recommended_refund_brl = 0.0
            primary_action = "reject_late_refund"
            root_cause_code = "DELIVERY_WITHIN_ESTIMATE"

        # Secondary Issues
        secondary_issues = []
        if order_facts["multi_item_order"]:
            secondary_issues.append("multi_item_order")
        if order_facts["multi_seller_order"]:
            secondary_issues.append("multi_seller_order")
        if pay_facts["split_payment"]:
            secondary_issues.append("split_payment")
        if cust_facts["repeat_customer"]:
            secondary_issues.append("repeat_customer")
        if order_facts["multiple_categories"]:
            secondary_issues.append("multiple_categories")

        case_status = "action_required" if recommended_refund_brl > 0 else "no_action"

        # Actions bổ sung
        resolution_actions = [primary_action]

        # 1. review_seller_handoff hoặc review_carrier_delay
        if len(late_handoff_seller_ids) > 0:
            resolution_actions.append("review_seller_handoff")
        elif delivery_variance_hours is not None and delivery_variance_hours > 0:
            resolution_actions.append("review_carrier_delay")

        # 2. verify_refund_completion
        if primary_issue in ["canceled_order_paid", "unavailable_order_paid"]:
            resolution_actions.append("verify_refund_completion")

        # 3. coordinate_multi_seller_case
        if order_facts["multi_seller_order"]:
            resolution_actions.append("coordinate_multi_seller_case")

        # 4. verify_payment_allocation
        if pay_facts["split_payment"] and primary_issue != "valid_split_payment":
            resolution_actions.append("verify_payment_allocation")

        # Giới hạn
        resolution_actions = resolution_actions[:5]

        # Evidence IDs
        evidence_ids = [f"order:{order_id}"]
        for item_id in order_facts["item_ids"]:
            evidence_ids.append(f"item:{item_id}")
        for pay_id in pay_facts["payment_ids"]:
            evidence_ids.append(f"payment:{pay_id}")
        for rp in responsible_parties:
            if rp["party_type"] == "seller":
                evidence_ids.append(f"seller:{rp['party_id']}")
        evidence_ids.append(f"policy:{root_cause_code}")
        
        # Giới hạn 20 evidence IDs
        evidence_ids = evidence_ids[:20]

        ranked_causes = [{"cause_code": root_cause_code, "rank": 1}]

        return {
            "case_assessment": {
                "primary_issue": primary_issue,
                "secondary_issues": secondary_issues,
                "case_status": case_status,
                "confidence": 1.0 # Các logic chặt chẽ dựa trên policy
            },
            "root_cause_analysis": {
                "ranked_causes": ranked_causes,
                "responsible_parties": responsible_parties
            },
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": clean_float(recommended_refund_brl)
            },
            "resolution_actions": resolution_actions,
            "evidence_ids": evidence_ids
        }


class VerifierAgent:
    def validate(self, case_id, final_json):
        # Validate schema và các giới hạn
        try:
            assert final_json.get("case_id") == case_id
            
            assessment = final_json.get("case_assessment", {})
            assert "primary_issue" in assessment
            assert "secondary_issues" in assessment
            assert assessment.get("case_status") in ["action_required", "no_action"]
            assert 0.0 <= assessment.get("confidence", 0.0) <= 1.0

            entities = final_json.get("affected_entities", {})
            assert len(entities.get("order_ids", [])) <= 5
            assert len(entities.get("item_ids", [])) <= 5
            assert len(entities.get("seller_ids", [])) <= 3
            assert len(entities.get("payment_ids", [])) <= 5

            cust_ctx = final_json.get("customer_context", {})
            assert len(cust_ctx.get("related_order_ids", [])) <= 5

            prod_ctx = final_json.get("product_context", {})
            assert len(prod_ctx.get("product_ids", [])) <= 5
            assert len(prod_ctx.get("category_names", [])) <= 5

            root_cause = final_json.get("root_cause_analysis", {})
            assert len(root_cause.get("ranked_causes", [])) <= 3
            assert len(root_cause.get("responsible_parties", [])) <= 3

            assert len(final_json.get("evidence_ids", [])) <= 20
            assert len(final_json.get("resolution_actions", [])) <= 5

            # Kiểm tra định dạng evidence_ids
            for ev_id in final_json.get("evidence_ids", []):
                parts = ev_id.split(":")
                assert parts[0] in ["order", "item", "payment", "seller", "policy"]

            return True, "Valid"
        except AssertionError as e:
            return False, f"Assertion failed: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"


class CoordinatorAgent:
    def __init__(self, db):
        self.db = db
        self.customer_agent = CustomerAgent(db)
        self.order_agent = OrderProductAgent(db)
        self.payment_agent = PaymentAgent(db)
        self.delivery_agent = DeliveryAgent(db)
        self.policy_agent = PolicyAgent()
        self.verifier = VerifierAgent()

    def process_ticket(self, ticket_data):
        case_id = ticket_data.get("case_id")
        cust_req = ticket_data.get("customer_request", {})
        order_id = cust_req.get("claimed_order_id")

        # Đọc thông tin order
        order_details = self.db.get_order_details(order_id)
        if not order_details:
            # Tạo output trống/fallback nếu order không tìm thấy
            return self.get_empty_fallback(case_id, order_id)

        customer_id = order_details.get("customer_id")

        # Kích hoạt các Agent và thực hiện Handoff
        # 1. Customer Agent
        cust_facts = self.customer_agent.process(order_id, customer_id)
        
        # 2. Order & Product Agent
        order_facts = self.order_agent.process(order_id)
        
        # 3. Payment Agent
        pay_facts = self.payment_agent.process(order_id, order_facts["items_raw"])
        
        # 4. Delivery Agent
        del_facts = self.delivery_agent.process(order_id, order_details, order_facts["items_raw"])
        
        # 5. Policy Agent
        policy_resolution = self.policy_agent.process(
            order_id, order_details, cust_facts, order_facts, pay_facts, del_facts
        )

        # Trộn kết quả
        final_json = {
            "case_id": case_id,
            "case_assessment": policy_resolution["case_assessment"],
            "affected_entities": {
                "order_ids": [order_id],
                "item_ids": order_facts["item_ids"],
                "seller_ids": order_facts["seller_ids"],
                "payment_ids": pay_facts["payment_ids"]
            },
            "customer_context": {
                "customer_unique_id": cust_facts["customer_unique_id"],
                "related_order_ids": cust_facts["related_order_ids"]
            },
            "product_context": {
                "product_ids": order_facts["product_ids"],
                "category_names": order_facts["category_names"]
            },
            "delivery_analysis": {
                "delivered_at": del_facts["delivered_at"],
                "estimated_delivery_at": del_facts["estimated_delivery_at"],
                "carrier_handoff_at": del_facts["carrier_handoff_at"],
                "delivery_variance_hours": del_facts["delivery_variance_hours"],
                "seller_handoff_analysis": del_facts["seller_handoff_analysis"],
                "late_handoff_seller_ids": del_facts["late_handoff_seller_ids"]
            },
            "payment_reconciliation": {
                "currency": "BRL",
                "item_total_brl": pay_facts["item_total_brl"],
                "freight_total_brl": pay_facts["freight_total_brl"],
                "expected_total_brl": pay_facts["expected_total_brl"],
                "payment_total_brl": pay_facts["payment_total_brl"],
                "difference_brl": pay_facts["difference_brl"],
                "reconciled": pay_facts["reconciled"],
                "payment_types": pay_facts["payment_types"]
            },
            "root_cause_analysis": policy_resolution["root_cause_analysis"],
            "evidence_ids": policy_resolution["evidence_ids"],
            "financial_resolution": policy_resolution["financial_resolution"],
            "resolution_actions": policy_resolution["resolution_actions"]
        }

        # 6. Verifier Agent
        is_valid, msg = self.verifier.validate(case_id, final_json)
        if not is_valid:
            print(f"Warning: Verification failed for {case_id}: {msg}")

        # Tạo trace log cho ticket này
        trace_log = {
            "case_id": case_id,
            "order_id": order_id,
            "steps": [
                {"agent": "CoordinatorAgent", "action": "received_ticket"},
                {"agent": "CustomerAgent", "action": "analyzed_customer_history", "facts": cust_facts},
                {"agent": "OrderProductAgent", "action": "analyzed_items_products", "facts": {k:v for k,v in order_facts.items() if k != "items_raw"}},
                {"agent": "PaymentAgent", "action": "reconciled_payment", "facts": pay_facts},
                {"agent": "DeliveryAgent", "action": "analyzed_delivery_dates", "facts": del_facts},
                {"agent": "PolicyAgent", "action": "applied_ec_policy_v2", "resolution": policy_resolution},
                {"agent": "VerifierAgent", "action": "verified_schema", "status": is_valid, "message": msg}
            ]
        }

        return final_json, trace_log

    def get_empty_fallback(self, case_id, order_id):
        fallback = {
            "case_id": case_id,
            "case_assessment": {
                "primary_issue": "unsupported_late_claim",
                "secondary_issues": [],
                "case_status": "no_action",
                "confidence": 0.5
            },
            "affected_entities": {
                "order_ids": [order_id] if order_id else [],
                "item_ids": [],
                "seller_ids": [],
                "payment_ids": []
            },
            "customer_context": {
                "customer_unique_id": None,
                "related_order_ids": []
            },
            "product_context": {
                "product_ids": [],
                "category_names": []
            },
            "delivery_analysis": {
                "delivered_at": None,
                "estimated_delivery_at": None,
                "carrier_handoff_at": None,
                "delivery_variance_hours": None,
                "seller_handoff_analysis": [],
                "late_handoff_seller_ids": []
            },
            "payment_reconciliation": {
                "currency": "BRL",
                "item_total_brl": None,
                "freight_total_brl": None,
                "expected_total_brl": None,
                "payment_total_brl": 0.0,
                "difference_brl": None,
                "reconciled": None,
                "payment_types": []
            },
            "root_cause_analysis": {
                "ranked_causes": [{"cause_code": "DELIVERY_WITHIN_ESTIMATE", "rank": 1}],
                "responsible_parties": []
            },
            "evidence_ids": [f"order:{order_id}"] if order_id else [],
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": 0.0
            },
            "resolution_actions": ["reject_late_refund"]
        }
        trace_log = {
            "case_id": case_id,
            "order_id": order_id,
            "status": "order_not_found_fallback"
        }
        return fallback, trace_log
