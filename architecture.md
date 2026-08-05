# Kiến trúc hệ thống multi-agent xử lý khiếu nại Olist

## 1. Luồng quyết định

Pipeline chuẩn nằm ở `run_pipeline.py`, sử dụng `CoordinatorAgent` trong `agents.py` và dữ liệu được index bởi `data_loader.py`. Mỗi ticket đi tuần tự qua các agent để bước sau chỉ nhận fact đã được dựng từ CSV:

```mermaid
flowchart LR
    I[Ticket JSON] --> C[Coordinator]
    C --> U[Customer]
    U --> O[Order & Product]
    O --> P[Payment]
    P --> D[Delivery]
    D --> R[Policy EC_POLICY_V2]
    R --> V[Verifier]
    V --> J[Output JSON + trace]
```

Hệ thống không dùng nội dung tự do trong khiếu nại để tạo fact. `claimed_order_id` là khóa truy vấn; quyết định cuối cùng do rule engine `EC_POLICY_V2` đưa ra. LLM dưới 10B là tùy chọn để bổ sung phân tích, không được phép thay đổi fact, policy decision hoặc evidence.

## 2. Vai trò, input và output

| Agent | Input | Dữ liệu được đọc | Output handoff |
|---|---|---|---|
| Coordinator | Ticket, `case_id`, `claimed_order_id` | Không đọc CSV trực tiếp | Điều phối, ghép JSON và trace |
| Customer | `order_id`, `customer_id` | customers, orders | `customer_unique_id`, lịch sử order, repeat flag |
| Order & Product | `order_id` | items, products, sellers | item/product/seller/category IDs và secondary flags |
| Payment | `order_id`, item rows | payments | payment IDs, tổng tiền, chênh lệch, reconciled |
| Delivery | `order_id`, order và item rows | orders, items | mốc giao hàng, variance, seller bàn giao muộn |
| Policy | Các fact từ bốn agent chuyên trách | `EC_POLICY_V2` trong code | issue, trách nhiệm, root cause, refund, actions, evidence |
| Verifier | Draft JSON | Không đọc nguồn mới | Trạng thái schema/constraint trước khi ghi file |

## 3. Handoff contract

Mỗi bước trong `trace.jsonl` ghi lại:

```json
{
  "ticket_id": "EC_001",
  "question": "Câu hỏi agent cần trả lời",
  "found_facts": {
    "source_id": "order/payment/item/seller/policy ID",
    "value": "fact được dựng từ dữ liệu"
  },
  "missing_or_contradictory_facts": null,
  "recommendation": "Bước hoặc agent nhận tiếp theo"
}
```

`ticket_id` trong trace cấp coordinator là `case_id`; các handoff chuyên môn có thể dùng `order_id` để định danh đối tượng đang điều tra. Fact thiếu được ghi rõ thay vì suy diễn. Agent nhận việc chỉ dùng `found_facts` và ID nguồn có thể truy vết.

## 4. Policy và evidence

`PolicyAgent` áp dụng `EC_POLICY_V2` theo đúng thứ tự ưu tiên:

1. `canceled_order_paid`
2. `unavailable_order_paid`
3. `late_delivery_seller`
4. `late_delivery_logistics`
5. `valid_split_payment`
6. `unsupported_late_claim`

Evidence chỉ nhận các dạng được phép:

- `order:<order_id>`
- `item:<order_id>:<order_item_id>`
- `payment:<order_id>:<payment_sequential>`
- `seller:<seller_id>`
- `policy:<root_cause_code>`

Không có item row thì các trường `expected_total_brl`, `difference_brl` và `reconciled` là `null`; các phân tích item/seller/product/category và seller handoff là mảng rỗng.

## 5. Verification và artefact nộp

`VerifierAgent` kiểm tra case ID, trường bắt buộc, enum, confidence, định dạng evidence và giới hạn mảng. Batch chuẩn có đúng 50 output và 50 dòng trace; từng trace chứa Coordinator, bốn agent dữ liệu, Policy và Verifier.

Chạy pipeline và đóng gói:

```bash
venv/bin/python run_pipeline.py
venv/bin/python make_zip.py
```

`submission.zip` chỉ chứa `output/EC_001.json` đến `output/EC_050.json`, `architecture.md`, `trace.jsonl` và `metadata.json`; không chứa `.env`, cache, virtual environment hoặc source code.
