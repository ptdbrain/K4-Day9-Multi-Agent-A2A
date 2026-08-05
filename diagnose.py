import os
import json
import pandas as pd
from data_loader import OlistDatabase
from agents import parse_date, get_variance_hours

def diagnose():
    db = OlistDatabase("data")
    input_dir = "input"
    tickets = sorted([f for f in os.listdir(input_dir) if f.endswith(".json")])
    
    print(f"Diagnosing {len(tickets)} tickets...")
    for t_file in tickets:
        t_path = os.path.join(input_dir, t_file)
        with open(t_path, "r", encoding="utf-8") as f:
            ticket = json.load(f)
            
        case_id = ticket.get("case_id")
        order_id = ticket.get("customer_request", {}).get("claimed_order_id")
        
        # Check order existence
        order = db.get_order_details(order_id)
        if not order:
            print(f"[{case_id}] Order {order_id} NOT found in orders dataset!")
            continue
            
        # Check status and timestamps
        status = order.get("order_status")
        delivered_at = order.get("order_delivered_customer_date")
        estimated = order.get("order_estimated_delivery_date")
        carrier_delivered = order.get("order_delivered_carrier_date")
        
        # Check items and payments
        items = db.get_order_items(order_id)
        payments = db.get_order_payments(order_id)
        
        # Tính toán các chỉ số
        p_total = sum(float(p.get("payment_value", 0)) for p in payments)
        
        if not items:
            print(f"[{case_id}] Order {order_id} has NO items! Status: {status}, Payments: {len(payments)} (Total: {p_total})")
            continue
            
        i_total = sum(float(i.get("price", 0)) for i in items)
        f_total = sum(float(i.get("freight_value", 0)) for i in items)
        expected = i_total + f_total
        diff = p_total - expected
        reconciled = abs(diff) <= 0.10
        
        dt_delivered = parse_date(delivered_at)
        dt_estimated = parse_date(estimated)
        dt_carrier = parse_date(carrier_delivered)
        
        delivery_variance = get_variance_hours(dt_delivered, dt_estimated)
        
        # Check late handoff
        late_handoffs = []
        for i in items:
            s_id = i.get("seller_id")
            limit_str = i.get("shipping_limit_date")
            limit = parse_date(limit_str)
            if limit and dt_carrier:
                h_var = get_variance_hours(dt_carrier, limit)
                if h_var > 0:
                    late_handoffs.append(s_id)
                    
        print(f"[{case_id}] Order: {order_id} | Status: {status} | Items: {len(items)} | Payments: {len(payments)} | Rec: {reconciled} | DelVar: {delivery_variance} | LateHandoff: {len(late_handoffs)}")

if __name__ == "__main__":
    diagnose()
