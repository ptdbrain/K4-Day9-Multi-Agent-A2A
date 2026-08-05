# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                    |
| --------------- | --------------------------- |
| Họ và tên       | Phan Trọng Đạt              |
| MSSV            | 2A202601138                 |
| Khóa/Lớp        | K4 / 2A                     |
| Vai trò chính   | Kiến trúc sư & Dev toàn pipeline |
| Ngày hoàn thành | 2026-08-05                  |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable      | File/hàm phụ trách                              | Input nhận vào                                | Output bàn giao                            | Trạng thái   |
| ----------------------- | ----------------------------------------------- | --------------------------------------------- | ------------------------------------------ | ------------ |
| DataLoader (singleton)  | `src/data_loader.py`                            | 9 CSV Olist                                   | Pandas DataFrames + query helpers          | Hoàn thành   |
| CustomerAgent           | `src/agents/customer_agent.py` → `run()`        | `case_id`, `order_id`                         | `customer_unique_id`, `related_order_ids`  | Hoàn thành   |
| OrderProductAgent       | `src/agents/order_product_agent.py` → `run()`   | `order_id`                                    | item_ids, seller_ids, product_ids, cats    | Hoàn thành   |
| PaymentAgent            | `src/agents/payment_agent.py` → `run()`         | `order_id`, `raw_items`                       | payment reconciliation dict                | Hoàn thành   |
| DeliveryAgent           | `src/agents/delivery_agent.py` → `run()`        | `order_id`, `raw_items`                       | delivery variance, seller handoff analysis | Hoàn thành   |
| PolicyAgent             | `src/agents/policy_agent.py` → `run()`          | outputs từ 4 agents trên                      | primary/secondary issues, refund, actions  | Hoàn thành   |
| VerifierAgent           | `src/agents/verifier_agent.py` → `run()`        | draft output dict                             | validated JSON tuân thủ schema             | Hoàn thành   |
| CoordinatorAgent        | `src/agents/coordinator_agent.py` → `process_case()` | case JSON                               | final output JSON                          | Hoàn thành   |
| Trace Logger            | `src/logger.py`                                 | các agent step                                | `trace.jsonl`                              | Hoàn thành   |
| Pipeline entry point    | `main.py`                                       | `input/EC_*.json`                             | `output/EC_*.json`, `trace.jsonl`          | Hoàn thành   |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                              | Thành viên/module được hỗ trợ | Kết quả                                        |
| -------------------------------------- | ----------------------------- | ---------------------------------------------- |
| Debug lỗi NaTType strftime             | DeliveryAgent                 | Fix `pd.isnull()` — 50/50 case thành công      |
| Thiết kế rule-based confidence scoring | CoordinatorAgent              | Loại bỏ LLM call → 50 case/1.4 giây thay vì ~17 phút |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện              | File/hàm/artifact liên quan              | Kết quả bàn giao                       | Cách xác minh                           |
| ---------------------------------- | ---------------------------------------- | -------------------------------------- | --------------------------------------- |
| Xây dựng toàn bộ multi-agent pipeline | `src/agents/*.py`, `main.py`           | 50 JSON output tuân thủ schema         | `python main.py` → Done. 50 succeeded  |
| Áp dụng đúng EC_POLICY_V2         | `src/agents/policy_agent.py`             | 6 primary issues được xử lý đúng      | Kiểm tra phân bố output                 |
| Tích hợp trace logging             | `src/logger.py`                          | `trace.jsonl` 129KB                    | `wc -l trace.jsonl` hoặc đọc file      |
| Viết architecture.md               | `architecture.md`                        | Sơ đồ ASCII đầy đủ 7 agent + handoff  | Xem `architecture.md`                   |

Phân bố primary issue trên 50 case thực tế:

| Primary issue              | Số case |
| -------------------------- | ------- |
| `late_delivery_seller`     | 10      |
| `late_delivery_logistics`  | 10      |
| `unsupported_late_claim`   | 8       |
| `canceled_order_paid`      | 8       |
| `valid_split_payment`      | 8       |
| `unavailable_order_paid`   | 6       |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Mỗi khiếu nại thương mại điện tử cần đối chiếu nhiều nguồn dữ liệu (order, items, payments, delivery timestamps, seller handoff) trước khi áp dụng policy. Không thể giải quyết chỉ từ một bảng CSV đơn lẻ — cần phân công, join dữ liệu và kiểm chứng trước khi kết luận.

### Cách triển khai

Pipeline áp dụng **sequential agent handoff** với data contract rõ ràng giữa từng bước:

1. **DataLoader** (singleton) load 9 CSV một lần duy nhất, build pandas DataFrame và các helper query. Tránh I/O lặp lại giữa các case.

2. **CustomerAgent** dùng `customer_unique_id` (không phải `customer_id`) để tìm lịch sử mua hàng thực sự qua nhiều đơn. Điều này quan trọng vì mỗi `customer_id` chỉ đại diện cho một order.

3. **DeliveryAgent** tính `handoff_variance_hours` theo công thức trong spec: lấy `order_delivered_carrier_date` trừ `shipping_limit_date` sớm nhất của từng seller. NaT timestamps được xử lý bằng `pd.isnull()` thay vì `isinstance(float)`.

4. **PolicyAgent** là pure rule engine — không có LLM. Áp dụng 6 điều kiện priority theo thứ tự: canceled → unavailable → late_seller → late_logistics → valid_split → unsupported. Secondary issues và actions theo đúng thứ tự spec.

5. **VerifierAgent** clamp mọi array về đúng giới hạn (item ≤5, seller ≤3, evidence ≤20) và validate format evidence ID trước khi ghi file.

6. **Confidence scoring** hoàn toàn rule-based (không gọi LLM) — dựa trên loại issue và delivery variance, với penalty khi thiếu timestamp hoặc payment không reconciled.

### Input, output và contract

| Thành phần              | Mô tả                                               |
| ----------------------- | --------------------------------------------------- |
| Input                   | `input/EC_*.json` theo schema spec (claimed_order_id) |
| Output                  | `output/EC_*.json` tuân thủ schema README section 6 |
| Module phụ thuộc        | `pandas`, `python-dotenv`, `tqdm`, `openai` (optional) |
| Module sử dụng output   | Chấm điểm tự động của ban tổ chức                   |
| Điều kiện lỗi cần xử lý | NaT timestamps, order không có items, order không tồn tại trong CSV |

### Cách xác minh

```bash
# Chạy toàn bộ 50 case
python main.py

# Kiểm tra 1 case cụ thể
python main.py --case EC_001

# Xem phân bố kết quả
python -c "
import json; from pathlib import Path; from collections import Counter
c = Counter(json.loads(f.read_text())['case_assessment']['primary_issue']
            for f in sorted(Path('output').glob('EC_*.json')))
[print(f'  {k}: {v}') for k, v in c.most_common()]
"
```

- **Kết quả mong đợi:** Done. 50 succeeded, 0 failed.
- **Kết quả thực tế:** 50/50 case thành công trong 1.4 giây.
- **Artifact/log:** `output/EC_001.json … EC_050.json`, `trace.jsonl`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Confidence scoring — nên dùng LLM hay rule-based?

- **Các phương án đã cân nhắc:**
  1. Gọi LLM (qwen/qwen3.5-9b qua OpenRouter) mỗi case → chính xác hơn nhưng 50 API call tuần tự.
  2. Rule-based deterministic scoring dựa trên delivery variance, payment reconciliation.

- **Phương án đã chọn:** Rule-based hoàn toàn.

- **Lý do:** Khi thử nghiệm với LLM, mỗi case tốn ~20 giây network latency → 50 case ≈ 17 phút. Rule-based hoàn thành trong 1.4 giây (nhanh hơn 700x). Quan trọng hơn, `confidence` không phải trường được rubric đánh giá riêng — nó nằm trong `case_assessment` chiếm 15% tổng điểm cùng với `primary_issue` và `secondary_issues`. Độ chính xác của data analysis mới là điểm cốt lõi.

- **Bằng chứng quyết định phù hợp:** 50/50 case thành công, không error, tốc độ có thể chạy nhiều lần trong thời gian competition.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```
  EC_004: ValueError: NaTType does not support strftime
  ```
  14/50 case thất bại với lỗi này.

- **Lệnh hoặc bước tái hiện:** `python main.py` → các case có `order_delivered_customer_date` là `NaT`.

- **Nguyên nhân gốc:** Hàm `_fmt()` trong `delivery_agent.py` check `isinstance(ts, float) and pd.isna(ts)` — điều kiện này **không bắt được `pd.NaT`** vì NaT có type là `NaTType`, không phải `float`. Khi gọi `ts.strftime(_FMT)` trên NaT, Python ném `ValueError`.

- **Cách xử lý:**
  ```python
  # Trước:
  if ts is None or (isinstance(ts, float) and pd.isna(ts)):
      return None

  # Sau:
  try:
      if pd.isnull(ts):   # pd.isnull() handles NaT, NaN, None
          return None
  except (TypeError, ValueError):
      pass
  try:
      return ts.strftime(_FMT)
  except (AttributeError, ValueError):
      ...
  ```

- **Cách xác minh sau khi sửa:** `python main.py` → Done. 50 succeeded, 0 failed.
- **Điều học được:** `pd.isnull()` là cách đúng để kiểm tra null cho mọi loại pandas — không nên giả định NaT là float.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ CSV đến output như thế nào?**
   `DataLoader` load 9 CSV vào pandas DataFrames một lần. Với mỗi case, `CoordinatorAgent` đọc `claimed_order_id` từ input JSON, sau đó lần lượt gọi 5 agent chuyên biệt để join và trích xuất dữ liệu liên quan. `PolicyAgent` nhận tất cả kết quả và áp dụng rules để đưa ra kết luận. `VerifierAgent` clamp arrays và validate trước khi ghi JSON.

2. **Evaluation set và ground-truth dùng để đo quality ra sao?**
   Ban tổ chức chấm điểm bằng so sánh tự động giữa `output/EC_*.json` và ground-truth. Mỗi trường được weighted: primary/secondary issues (15%), affected entities (15%), delivery analysis (15%), payment reconciliation (15%), root cause & evidence (15%), customer/product context (15%), financial resolution & actions (10%).

3. **Quality checks trong bài lab:**
   `VerifierAgent` làm vai trò quality gate: kiểm tra array limits, evidence ID format (prefix phải là `order`, `item`, `payment`, `seller`, `policy`), clamp `confidence` về `[0, 1]`. Ngoài ra `DataLoader` kiểm tra NaT timestamps trước khi tính variance.

4. **Vì sao cùng một test set cho mọi điều kiện?**
   Để kết quả có thể so sánh được. Nếu dùng test set khác nhau cho từng trường hợp, không biết được improvement đến từ model hay từ data.

5. **Repair được xem là thành công dựa trên gì?**
   `50/50 case` output hợp lệ, không có error. Evidence IDs đúng format và có thể truy nguyên từ CSV. Timestamps giữ nguyên format `YYYY-MM-DD HH:MM:SS` hoặc `null`. Arrays trong giới hạn spec.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phan Trọng Đạt
**Ngày xác nhận:** 2026-08-05
