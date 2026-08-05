# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                    |
| --------------- | --------------------------- |
| Họ và tên       | Bùi Thu Trang               |
| MSSV            | 2A202601758                    |
| Khóa/Lớp        | K4                          |
| Vai trò chính   | Kỹ sư xử lý dữ liệu (Payment & Policy Agent) |
| Ngày hoàn thành | 2026-08-05                  |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable      | File/hàm phụ trách                              | Input nhận vào                                | Output bàn giao                            | Trạng thái   |
| ----------------------- | ----------------------------------------------- | --------------------------------------------- | ------------------------------------------ | ------------ |
| PaymentAgent            | `src/agents/payment_agent.py` → `run()`         | `order_id`, `raw_items`                       | payment reconciliation dict                | Hoàn thành   |
| PolicyAgent             | `src/agents/policy_agent.py` → `run()`          | outputs tổng hợp từ các agent khác (Customer, Order, Payment, Delivery) | primary/secondary issues, refund, actions  | Hoàn thành   |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                              | Thành viên/module được hỗ trợ | Kết quả                                        |
| -------------------------------------- | ----------------------------- | ---------------------------------------------- |
| Tối ưu logic đối soát thanh toán       | OrderProductAgent             | Xử lý mượt mà các trường hợp order không có item (trả về null thay vì lỗi toán học) |
| Chuẩn hóa dữ liệu đầu ra policy        | VerifierAgent                 | Đảm bảo đúng định dạng mảng (actions, issues) và giới hạn số lượng phần tử đầu ra. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện              | File/hàm/artifact liên quan              | Kết quả bàn giao                       | Cách xác minh                           |
| ---------------------------------- | ---------------------------------------- | -------------------------------------- | --------------------------------------- |
| Phát triển PaymentAgent để đối soát thanh toán | `src/agents/payment_agent.py` | Tính toán chính xác chênh lệch thanh toán và trạng thái reconciled | Xác minh trường `payment_reconciliation` trong JSON output |
| Chuyển hóa bộ luật EC_POLICY_V2 thành code | `src/agents/policy_agent.py` | Trích xuất chính xác primary issue, secondary issues, responsible parties | Kiểm tra output các rule dựa trên spec |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:
Phần việc của mình tạo ra trực tiếp kết quả đánh giá (case assessment) và định hướng xử lý tài chính (financial resolution) trong toàn bộ 50 file JSON. Mọi quyết định về refund và bên chịu trách nhiệm đều đi qua PolicyAgent do mình thiết kế.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Bài toán yêu cầu tính toán chi tiết giá trị thanh toán thực tế của khách hàng so với tổng giá trị mặt hàng và phí ship. Sau đó, dựa trên toàn bộ bối cảnh (thanh toán, thời gian giao hàng, trạng thái đơn, lịch sử khách hàng), hệ thống phải xác định nguyên nhân cốt lõi (primary issue) và các vấn đề phụ theo một bộ quy tắc ngặt nghèo (EC_POLICY_V2).

### Cách triển khai

1. **PaymentAgent**: Mình tính toán `expected_total_brl` = tổng `price` + tổng `freight_value`. Sau đó đối soát với `payment_total_brl` (tổng các khoản thanh toán). Nếu độ lệch tuyệt đối <= 0.10 BRL, đánh dấu là `reconciled`. Mình xử lý kỹ edge case: nếu không có item nào, các trường tính toán phải set là `None`.
2. **PolicyAgent**: Mình tổ chức code thành một Rule Engine tuần tự.
   - Các `primary_issue` được đánh giá theo đúng thứ tự: Canceled -> Unavailable -> Late (Seller) -> Late (Logistics) -> Valid Split -> Unsupported.
   - Các `secondary_issues` được kiểm tra độc lập và append vào mảng theo đúng thứ tự (multi_item -> multi_seller -> split_payment -> repeat_customer -> multiple_categories).
   - Logic `resolution_actions` cũng được gán theo chuỗi rule if-else tương ứng.

### Input, output và contract

| Thành phần              | Mô tả                                               |
| ----------------------- | --------------------------------------------------- |
| Input                   | `raw_items`, `payments`, thông tin delivery, order status |
| Output                  | Dictionary chứa assessment, evidence_ids, financial_resolution, actions |
| Module phụ thuộc        | Data Loader (để truy vấn database)                  |
| Module sử dụng output   | CoordinatorAgent (để gộp thành file JSON cuối cùng) |
| Điều kiện lỗi cần xử lý | Xử lý order không có payment hoặc không có item     |

### Cách xác minh

```bash
python main.py
```

- **Kết quả mong đợi:** Code sinh ra JSON hợp lệ cho cả 50 case, PaymentAgent không crash khi gặp số chia/trừ null, PolicyAgent phân loại đủ 6 loại primary issue.
- **Kết quả thực tế:** 50 file JSON được tạo thành công, có đủ primary issue, đối soát thanh toán chính xác, chạy rất nhanh (rule-based).
- **Artifact/log:** `output/*.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Triển khai PolicyAgent. Việc xử lý rule khá rắc rối vì có nhiều điều kiện đan xen (đơn hủy, đơn giao trễ, đối soát dòng tiền).
- **Các phương án đã cân nhắc:**
  1. Dùng LLM prompt để nhồi toàn bộ logic EC_POLICY_V2 vào và bắt LLM tự suy luận.
  2. Viết bằng Python if-else (Rule-based) để có kết quả deterministic.
- **Phương án đã chọn:** Rule-based (If-else) trong PolicyAgent.
- **Lý do:** Trade-off về correctness và cost/speed. LLM xử lý toán học và reasoning nhiều lớp thường hay bị ảo giác (hallucinate) sai 1-2 case (đặc biệt trong việc so sánh chuỗi ngày tháng hay sai số 0.10 BRL). Viết rule bằng Python đảm bảo độ chính xác tuyệt đối 100% dựa trên dữ liệu cứng và xử lý với tốc độ chớp nhoáng (chưa tới 1 giây cho 50 cases).
- **Bằng chứng quyết định phù hợp:** Kết quả `trace.jsonl` ghi nhận chạy không có exception, không bị rate-limit, output hoàn toàn ổn định qua nhiều lần chạy.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  Lỗi logic: Order không có item (trống `raw_items`) khiến phần tính tổng `price` trong PaymentAgent trả về sai logic so với spec (spec yêu cầu phải là `null`).
- **Lệnh hoặc bước tái hiện:** Chạy thử trên case bị lỗi data (đơn chưa có item nào).
- **Nguyên nhân gốc:** Hàm `sum()` của list rỗng trong Python trả về `0`. Nếu tính `0 - 0 = 0` thì `difference_brl` = 0 và `reconciled` = True, điều này sai hoàn toàn so với yêu cầu bài toán (bài toán yêu cầu nếu không có item thì expected_total, difference, reconciled phải là `null`).
- **Cách xử lý:**
  Sửa lại logic trong `PaymentAgent` kiểm tra độ dài list `raw_items` trước khi tính toán.
  ```python
  if not raw_items:
      # Set tất cả các trường tính toán thành None
      result["expected_total_brl"] = None
      # ...
  else:
      # Thực hiện sum và trừ bình thường
  ```
- **Cách xác minh sau khi sửa:** Chạy lại `python main.py` và kiểm tra JSON output của case lỗi, đảm bảo các trường `expected_total_brl`, `difference_brl` và `reconciled` là `null`.
- **Điều học được:** Khi xử lý dữ liệu tài chính, `0` và `null/None` mang ý nghĩa hoàn toàn khác biệt. Phải đọc rất kỹ spec trước khi mặc định return `0` cho exception.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ CSV đến output như thế nào?**
   Các agent độc lập lấy dữ liệu từ `DataLoader` (đã nạp CSV). `CoordinatorAgent` điều phối luồng: trước tiên gọi `CustomerAgent`, tiếp đó gọi `OrderProductAgent`, truyền kết quả cho `PaymentAgent` và `DeliveryAgent` xử lý song song, sau cùng gom lại đưa vào `PolicyAgent` quyết định lỗi rồi chuyển cho `VerifierAgent` chuẩn hóa xuất JSON.
2. **Evaluation set và ground-truth dùng để đo quality ra sao?**
   50 case input đại diện cho nhiều góc độ nghiệp vụ (giao trễ, hủy đơn, lỗi đối soát). Ground-truth JSON chứa đáp án chính xác của con người. Pipeline sẽ so khớp output với ground truth và cho điểm từng block (Payment 15%, Policy 15%...).
3. **Quality checks trong bài lab:**
   Các ràng buộc mảng không vượt quá giới hạn (ví dụ tối đa 5 payment_ids), dữ liệu NULL xử lý đúng chuẩn `null` của JSON thay vì NaN hay chuỗi "NaT", đảm bảo logic không sụp đổ vì thiếu data.
4. **Vì sao cùng một test set cho mọi điều kiện?**
   Để duy trì tính công bằng (baseline đo lường) và xác nhận mọi component trong luồng agent xử lý ổn định. Thay đổi đầu vào sẽ làm rối kết quả, không rõ hệ thống hỏng do thuật toán hay do dữ liệu mới.
5. **Repair được xem là thành công dựa trên gì?**
   Hệ thống không bị crash, 50 file JSON xuất ra hợp lệ về schema và logic nghiệp vụ. Thời gian chạy tối ưu, không có dấu vết ảo giác từ dữ liệu.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Bùi Thu Trang
**Ngày xác nhận:** 2026-08-05
