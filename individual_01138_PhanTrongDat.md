# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Phan Trọng Đạt |
| MSSV | 2A202601138 |
| Khóa/Lớp | K4 / 2A |
| Vai trò chính | Kiến trúc sư, Coordinator và tích hợp pipeline |
| Ngày hoàn thành | 2026-08-05 |

## 2. Phạm vi công việc

| Phần việc | File/hàm chính | Input | Output bàn giao |
|---|---|---|---|
| Điều phối agent | `agents.py` — `CoordinatorAgent` | Ticket K4 | Final JSON và trace theo ticket |
| Truy xuất dữ liệu | `data_loader.py` | CSV Olist | Order, customer, item và payment facts |
| Luồng batch | `run_pipeline.py` | `input/EC_*.json` | 50 JSON và `trace.jsonl` |
| Kiến trúc/handoff | `architecture.md` | Trách nhiệm của 7 agent | Sơ đồ, I/O và evidence contract |

Tôi phối hợp với Phạm Quốc Minh ở phần tích hợp/verifier và với Bùi Thu Trang ở phần Payment/Policy. Pipeline chuẩn của nhóm là `run_pipeline.py`; các agent chạy tuần tự để fact của bước trước trở thành input rõ ràng cho bước sau.

## 3. Kết quả và bằng chứng

- Coordinator điều phối đủ 7 vai trò: Coordinator, Customer, Order & Product, Payment, Delivery, Policy và Verifier.
- Mỗi handoff trong `trace.jsonl` có `ticket_id`, câu hỏi, `found_facts`, fact thiếu/mâu thuẫn và đề xuất bước tiếp theo.
- Mỗi `found_facts` có `order_id` làm ID nguồn; quyết định Policy có thêm evidence item, payment, seller và policy tương ứng.
- Batch thực tế tạo đúng 50 JSON và 50 dòng trace; lần kiểm tra cuối xác nhận 50/50 output khớp kết quả pipeline trong bộ nhớ.

Lệnh tái hiện:

```bash
venv/bin/python run_pipeline.py
venv/bin/python run_pipeline.py --ticket EC_001
venv/bin/python make_zip.py
```

## 4. Giải thích kỹ thuật

Coordinator chỉ lấy `claimed_order_id` từ nội dung ticket và không dùng mô tả tự do để tạo fact. Luồng xử lý là:

1. CustomerAgent tìm `customer_unique_id` và lịch sử order.
2. OrderProductAgent lấy item, seller, product và category.
3. PaymentAgent đối soát tổng payment với item + freight.
4. DeliveryAgent tính delivery variance và seller handoff variance.
5. PolicyAgent áp dụng `EC_POLICY_V2` theo thứ tự ưu tiên.
6. VerifierAgent kiểm tra schema, enum, evidence và giới hạn mảng.
7. Coordinator ghi output và một trace có thể kiểm tra cho ticket.

Thiết kế dùng rule-based cho fact, tính toán và quyết định tài chính. Model cấu hình là `qwen2.5:7b-instruct-q3_K_S` (dưới 10B), nhưng LLM là tùy chọn và không được dùng trong trace nộp bài.

## 5. Quyết định kỹ thuật quan trọng

Tôi chọn handoff tuần tự có contract thay vì để nhiều agent tự suy luận độc lập. Cách này giữ thứ tự dữ liệu nguồn ổn định, tránh mỗi agent parse ngày/tiền theo một cách khác và giúp trace phản ánh đúng input/output của từng bước. Policy vẫn tập trung ở một rule engine nên sửa một nguyên nhân sẽ áp dụng cho mọi ticket.

## 6. Lỗi đã xử lý

Một số order bị hủy hoặc chưa hoàn tất không có `order_delivered_carrier_date`. Nếu DeliveryAgent vẫn tính seller handoff, kết quả có thể lỗi hoặc tạo fact giả. Cách xử lý là kiểm tra timestamp tại DeliveryAgent; khi thiếu carrier handoff thì giữ `seller_handoff_analysis` và `late_handoff_seller_ids` rỗng. Sau sửa, batch chạy đủ 50 ticket và output vẫn qua verifier.

## 7. Hiểu biết end-to-end

- Grounding: mọi ID trong output phải dựng được từ CSV hoặc danh sách policy hợp lệ.
- Policy: refund, responsibility và action chỉ do `EC_POLICY_V2` quyết định.
- Quality gate: output phải parse được, đúng giới hạn và có evidence tồn tại.
- Artefact nộp: `submission.zip` gồm 50 JSON dưới `output/`, `architecture.md`, `trace.jsonl` và `metadata.json`; không có secret, cache hay virtual environment.

## 8. Cam kết

- [x] Báo cáo phản ánh pipeline và artefact hiện tại của nhóm.
- [x] Tôi có thể giải thích luồng end-to-end và phần việc của mình.
- [x] Không ghi API key, token hoặc secret.
- [x] Không khẳng định chất lượng bằng số liệu chưa được kiểm chứng.

**Họ và tên:** Phan Trọng Đạt

**Ngày xác nhận:** 2026-08-05
