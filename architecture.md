# Architecture — Multi-Agent E-commerce Dispute Resolution

## 1. Tổng quan hệ thống

Hệ thống gồm **7 agent chuyên biệt** phối hợp để xử lý 50 case khiếu nại. Mỗi agent chỉ truy cập dữ liệu trong domain của mình và handoff kết quả có cấu trúc cho agent tiếp theo. Mô hình sử dụng: **gemini-2.0-flash-lite** (≤ 10B parameters, qua Google AI API).

## 2. Sơ đồ luồng Agent

```
                        ┌─────────────────────┐
                        │   CoordinatorAgent  │  ← Nhận case JSON từ input/
                        │  (Orchestrator)     │
                        └──────────┬──────────┘
                                   │ handoff: order_id, case_id
             ┌─────────────────────┼───────────────────────┐
             │                     │                       │
             ▼                     ▼                       ▼
    ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │  CustomerAgent  │  │ OrderProductAgent│  │  PaymentAgent    │
    │                 │  │                  │  │                  │
    │ • customer_id   │  │ • order_status   │  │ • payment rows   │
    │ • unique_id     │  │ • item_ids       │  │ • item_total     │
    │ • related orders│  │ • seller_ids     │  │ • freight_total  │
    └────────┬────────┘  │ • product_ids    │  │ • reconciled     │
             │           │ • category_names │  └────────┬─────────┘
             │           │ • raw_items      │           │
             │           └────────┬─────────┘           │
             │                    │                     │
             │           ┌────────▼─────────┐           │
             │           │  DeliveryAgent   │           │
             │           │                  │           │
             │           │ • delivery_var   │           │
             │           │ • handoff_var    │           │
             │           │ • late_sellers   │           │
             │           └────────┬─────────┘           │
             │                    │                     │
             └──────────┬─────────┘─────────────────────┘
                        │ handoff: tất cả kết quả từ 4 agents
                        ▼
             ┌──────────────────────┐
             │     PolicyAgent      │
             │  (EC_POLICY_V2)      │
             │                      │
             │ • primary_issue      │
             │ • secondary_issues   │
             │ • responsible_parties│
             │ • refund_brl         │
             │ • resolution_actions │
             └──────────┬───────────┘
                        │ handoff: policy decision
                        ▼
             ┌──────────────────────┐
             │  CoordinatorAgent    │
             │  (Assembly + LLM)    │
             │                      │
             │ • Gọi LLM để tính   │
             │   confidence score   │
             │ • Build evidence_ids │
             │ • Assemble output    │
             └──────────┬───────────┘
                        │ handoff: draft output JSON
                        ▼
             ┌──────────────────────┐
             │   VerifierAgent      │
             │                      │
             │ • Clamp array limits │
             │ • Validate evidence  │
             │ • Null handling      │
             └──────────┬───────────┘
                        │
                        ▼
                  output/EC_XXX.json
```

## 3. Vai trò và quyền truy cập dữ liệu

| Agent | CSV truy cập | Input nhận | Output bàn giao |
|---|---|---|---|
| **CoordinatorAgent** | Không | Case JSON | Final output JSON |
| **CustomerAgent** | `customers`, `orders` | `order_id` | `customer_unique_id`, `related_order_ids` |
| **OrderProductAgent** | `orders`, `order_items`, `products`, `sellers`, `category_translation` | `order_id` | `item_ids`, `seller_ids`, `product_ids`, `category_names`, `raw_items` |
| **PaymentAgent** | `order_payments` | `order_id`, `raw_items` | Payment reconciliation data |
| **DeliveryAgent** | `orders` | `order_id`, `raw_items` | Delivery variance, seller handoff analysis |
| **PolicyAgent** | Không (rule engine) | Outputs từ 4 agent trên | `primary_issue`, `secondary_issues`, `responsible_parties`, `refund_brl`, `actions` |
| **VerifierAgent** | Không | Draft output | Validated output JSON |

## 4. Luồng Handoff chi tiết

```
CoordinatorAgent.process_case(case)
  │
  ├─► CustomerAgent.run(case_id, order_id)
  │         └─► return {customer_unique_id, related_order_ids}
  │
  ├─► OrderProductAgent.run(case_id, order_id)
  │         └─► return {order_status, item_ids, seller_ids, product_ids,
  │                      category_names, raw_items}
  │
  ├─► PaymentAgent.run(case_id, order_id, raw_items)
  │         └─► return {payment_ids, payment_types, item_total_brl,
  │                      freight_total_brl, expected_total_brl,
  │                      payment_total_brl, difference_brl, reconciled}
  │
  ├─► DeliveryAgent.run(case_id, order_id, raw_items)
  │         └─► return {delivered_at, estimated_delivery_at, carrier_handoff_at,
  │                      delivery_variance_hours, seller_handoff_analysis,
  │                      late_handoff_seller_ids, is_late_delivery, any_seller_late}
  │
  ├─► PolicyAgent.run(case_id, order_id, order_status, raw_items,
  │                    payments_data, delivery_data, customer_data,
  │                    order_product_data)
  │         └─► return {primary_issue, secondary_issues, case_status,
  │                      responsible_parties, root_cause_code,
  │                      refund_brl, resolution_actions}
  │
  ├─► [LLM gemini-2.0-flash-lite] estimate_confidence()
  │         └─► return confidence: float ∈ [0.0, 1.0]
  │
  ├─► Assemble draft output dict
  │
  └─► VerifierAgent.run(case_id, draft)
            └─► return validated final JSON → write to output/
```

## 5. Model và cấu hình

| Thành phần | Chi tiết |
|---|---|
| **Model** | `gemini-2.0-flash-lite` |
| **Provider** | Google AI API |
| **Parameter size** | ≤ 10B (distilled) |
| **LLM call per case** | 1 lần (confidence estimation) |
| **Fallback** | Rule-based confidence nếu API không khả dụng |
| **API Key** | Từ `.env` → `GEMINI_API_KEY` |
| **Trace** | `trace.jsonl` (truncate mỗi lần chạy mới) |

## 6. Cây thư mục

```
K4-Day9-Multi-Agent-A2A/
├── data/                        # 9 CSV files Olist (không commit)
├── input/                       # EC_001.json … EC_050.json (từ BTC)
├── output/                      # EC_001.json … EC_050.json (kết quả)
├── logging/                     # Reserved
├── src/
│   ├── __init__.py
│   ├── data_loader.py           # Singleton CSV loader
│   ├── logger.py                # Trace JSONL logger
│   └── agents/
│       ├── __init__.py
│       ├── base_agent.py        # BaseAgent (DataLoader + TraceLogger)
│       ├── customer_agent.py
│       ├── order_product_agent.py
│       ├── payment_agent.py
│       ├── delivery_agent.py
│       ├── policy_agent.py      # EC_POLICY_V2 rule engine
│       ├── verifier_agent.py
│       └── coordinator_agent.py # Orchestrator
├── main.py                      # Entry point
├── trace.jsonl                  # Runtime trace (generated)
├── metadata.json                # Model/framework info
├── architecture.md              # (this file)
├── individual_5SoCuoiMHV_HoVaTen.md
├── requirements.txt
└── .env                         # GEMINI_API_KEY (NOT committed)
```
