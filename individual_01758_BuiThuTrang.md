# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Bùi Thu Trang |
| MSSV | 2A202601758 |
| Khóa/Lớp | K4 / 2A |
| Vai trò chính | Kỹ sư Payment và Policy |
| Ngày hoàn thành | 2026-08-05 |

## 2. Phạm vi công việc

| Phần việc | File/hàm chính | Input | Output bàn giao |
|---|---|---|---|
| Đối soát thanh toán | `agents.py` — `PaymentAgent` | `order_id`, item rows, payment rows | Tổng tiền, chênh lệch, reconciled, payment IDs |
| Áp dụng policy | `agents.py` — `PolicyAgent` | Customer/Order/Payment/Delivery facts | Issue, responsibility, refund, root cause, actions |
| Edge-case dữ liệu | Payment/Policy handoff | Order thiếu item hoặc nhiều payment | Null handling và quyết định ổn định |

Tôi phối hợp với Phan Trọng Đạt ở Coordinator/Delivery và với Phạm Quốc Minh ở Verifier/integration. Các thay đổi của tôi nằm trong pipeline chuẩn `run_pipeline.py` và được kiểm tra trên toàn bộ 50 ticket.

## 3. Kết quả và bằng chứng

- `payment_total_brl` là tổng mọi payment row; `expected_total_brl` là tổng item + freight; `reconciled` dùng sai số `<= 0.10 BRL`.
- Payment ID giữ thứ tự `payment_sequential`; secondary issues và actions giữ thứ tự của `EC_POLICY_V2`.
- PolicyAgent áp dụng đủ sáu primary issue theo đúng priority và chỉ hoàn tiền theo dữ liệu đã đối soát.
- Kiểm tra cuối xác nhận 50/50 output khớp pipeline, schema/evidence có 0 lỗi và trace có đủ Policy/Verifier cho 50 case.

Lệnh tái hiện:

```bash
venv/bin/python run_pipeline.py
venv/bin/python run_pipeline.py --ticket EC_001
```

## 4. Giải thích kỹ thuật

PaymentAgent tính:

```text
expected_total_brl = sum(price) + sum(freight_value)
difference_brl     = payment_total_brl - expected_total_brl
reconciled         = abs(difference_brl) <= 0.10
```

Khi order không có item, `item_total_brl` và `freight_total_brl` là `0.0`; `expected_total_brl`, `difference_brl` và `reconciled` là `null`. Cách biểu diễn này phân biệt “không có cơ sở để đối soát” với “đã đối soát và chênh lệch bằng 0”.

PolicyAgent là rule engine tuần tự:

1. canceled paid
2. unavailable paid
3. late delivery do seller
4. late delivery do logistics
5. valid split payment
6. unsupported late claim

Sau primary issue, agent thêm secondary issues và actions đúng business order, dựng root-cause policy ID và chỉ thêm seller evidence khi seller chịu trách nhiệm.

## 5. Quyết định kỹ thuật quan trọng

Tôi chọn Python rule-based thay vì đưa logic tài chính vào prompt. Phép cộng tiền, ngưỡng 0.10 BRL và priority policy cần deterministic để cùng input luôn cho cùng output. Model `qwen2.5:7b-instruct-q3_K_S` (dưới 10B) vẫn được cấu hình tùy chọn, nhưng không tham gia quyết định tài chính hay trace nộp bài.

## 6. Lỗi đã xử lý

Với `raw_items` rỗng, `sum([])` trả về 0; nếu tiếp tục tính, hệ thống sẽ tạo `difference_brl = 0` và `reconciled = true`, tức là biến dữ liệu thiếu thành một fact đối soát giả. Tôi thêm nhánh xử lý tại PaymentAgent để ba trường phụ thuộc vào item trở thành `null`, trong khi tổng item/freight vẫn giữ `0.0` theo schema K4. Batch sau sửa chạy đủ 50 ticket và không cần sửa tay output.

## 7. Hiểu biết end-to-end

- Customer và Order agent cung cấp identity/item/product context.
- Payment và Delivery agent cung cấp fact tài chính/thời gian.
- PolicyAgent quyết định theo V2, không dựa vào lời khiếu nại tự do.
- Coordinator ghép evidence IDs; Verifier kiểm tra schema và limits.
- Một ticket lỗi phải được sửa ở Payment/Policy hoặc contract chung rồi chạy lại, không sửa JSON kết quả bằng tay.

## 8. Cam kết

- [x] Báo cáo phản ánh pipeline và artefact hiện tại của nhóm.
- [x] Tôi có thể giải thích luồng end-to-end và phần việc của mình.
- [x] Không ghi API key, token hoặc secret.
- [x] Không khẳng định chất lượng bằng số liệu chưa được kiểm chứng.

**Họ và tên:** Bùi Thu Trang

**Ngày xác nhận:** 2026-08-05
