# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Phạm Quốc Minh |
| MSSV | 2A202601494 |
| Khóa/Lớp | K4 / 2A |
| Vai trò chính | Developer — agent integration, verifier và đóng gói |
| Ngày hoàn thành | 2026-08-05 |

## 2. Phạm vi công việc

| Phần việc | File/hàm chính | Input | Output bàn giao |
|---|---|---|---|
| Thiết lập môi trường | `requirements.txt`, `.gitignore` | Python project | Bộ phụ thuộc và quy tắc loại secret/cache |
| Tích hợp agent | `agents.py`, `run_pipeline.py` | Fact từ Olist | Pipeline 50 ticket |
| Verification | `agents.py` — `VerifierAgent` | Draft JSON | Kết quả schema/constraint |
| Đóng gói | `make_zip.py`, `metadata.json` | Output và artefact bắt buộc | `submission.zip` |

Tôi phối hợp với Phan Trọng Đạt ở Coordinator/architecture và với Bùi Thu Trang ở Payment/Policy. Nhóm thống nhất dùng một pipeline chuẩn là `run_pipeline.py`, không dùng các entry point thử nghiệm để tạo artefact nộp.

## 3. Kết quả và bằng chứng

- Môi trường dùng `pandas`, `openai`, `python-dotenv` và `tqdm`; API client là tùy chọn, không cần để chạy rule engine.
- Verifier kiểm tra case ID, trường bắt buộc, confidence, evidence prefix và giới hạn mảng.
- Kiểm tra cuối xác nhận đúng 50 JSON, mọi file parse được, evidence ID tồn tại trong dữ liệu nguồn/policy và hai bản trace giống nhau.
- `submission.zip` có đúng 53 entry: 50 output, `architecture.md`, `trace.jsonl`, `metadata.json`; ZIP qua kiểm tra toàn vẹn.

Lệnh tái hiện:

```bash
venv/bin/python run_pipeline.py
venv/bin/python make_zip.py
unzip -t submission.zip
```

## 4. Giải thích kỹ thuật

Pipeline dùng DataLoader nạp và index dữ liệu một lần, sau đó Coordinator chuyển ticket tuần tự qua các agent chuyên trách. Mỗi agent chỉ tạo fact trong domain của mình; PolicyAgent tổng hợp theo `EC_POLICY_V2`; Verifier là quality gate trước khi ghi JSON.

`make_zip.py` kiểm tra đủ dải tên `EC_001.json` đến `EC_050.json`, parse toàn bộ JSON/JSONL rồi mới tạo ZIP. Script chỉ thêm các artefact được yêu cầu, vì vậy `.env`, source, cache và `venv/` không thể lọt vào gói nộp.

Model khai báo thống nhất trong code và metadata là `qwen2.5:7b-instruct-q3_K_S` (dưới 10B). Trace nộp bài dùng chế độ deterministic rule-based, không gọi LLM.

## 5. Quyết định kỹ thuật quan trọng

Tôi chọn verifier và packager deterministic thay vì dùng LLM để sửa output. LLM không phù hợp với kiểm tra tên file, JSON schema, giới hạn mảng hay phép tính tiền. Code xác định lỗi chính xác, có thể chạy lại và buộc nhóm sửa nguyên nhân ở agent/router thay vì sửa tay kết quả.

## 6. Lỗi đã xử lý

Khi cài package vào Python hệ thống, môi trường trả lỗi `externally-managed-environment` theo PEP 668. Tôi chuyển sang virtual environment cục bộ và ghi dependency trong `requirements.txt`, tránh thay đổi Python của hệ điều hành.

Trong bước đóng gói, ZIP cũ chỉ chứa output và thiếu ba artefact bắt buộc. Script hiện tại tạo `submission.zip` đúng cấu trúc, dừng ngay nếu thiếu file hoặc JSON/JSONL lỗi, rồi kiểm tra được bằng `unzip -t`.

## 7. Hiểu biết end-to-end

- Input trust boundary là ticket JSON; hệ thống chỉ dùng `claimed_order_id` để truy vấn.
- Fact được dựng từ CSV và chuyển tiếp kèm ID nguồn trong trace.
- Policy quyết định issue, trách nhiệm, refund và action.
- Verifier không che lỗi nghiệp vụ; nó từ chối hoặc giới hạn dữ liệu sai contract.
- Gói nộp tách khỏi source và không chứa secret/cache.

## 8. Cam kết

- [x] Báo cáo phản ánh pipeline và artefact hiện tại của nhóm.
- [x] Tôi có thể giải thích luồng end-to-end và phần việc của mình.
- [x] Không ghi API key, token hoặc secret.
- [x] Không khẳng định chất lượng bằng số liệu chưa được kiểm chứng.

**Họ và tên:** Phạm Quốc Minh

**Ngày xác nhận:** 2026-08-05
