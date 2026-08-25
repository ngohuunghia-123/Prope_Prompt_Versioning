# Development Journal — Team P-113 (Prope)

> Nhật ký phát triển: mỗi tuần ghi lại mục tiêu, việc đã làm, khó khăn & cách giải, bài học.
> Mốc lấy từ git log; thành viên bổ sung trải nghiệm cá nhân của mình vào từng tuần.

---

## Tuần 1 (24/07 – 02/08): Khởi động & định hình bài toán

- **Đã làm:** Initial commit (24/07); khảo sát 11 đội/nhân sự nội bộ về cách lưu prompt hiện tại; dựng khung repo, thiết lập logging AI (ai-log) từ 01/08.
- **Khó khăn & giải pháp:** Mọi người giữ prompt trong chat history/Sheets, không ai nói được revision nào đang chạy → chốt hướng đi: registry revision bất biến + approval gate + gateway OpenAI-compatible.
- **Bài học:** Xác định đúng "root problem" (mất ownership/provenance/trust) trước khi viết dòng code nào giúp mọi decision sau đó dễ hơn.

## Tuần 2 (03/08 – 09/08): Khóa thiết kế trước khi build

- **Đã làm:** Viết bộ tài liệu đặc tả trong `docs/` — 8 module specs (`docs/modules/*.lock.yml`), assumptions A-001→A-151, open questions; ngày 09/08 chạy agent sweep tổng hợp thành `docs/AGENT_CONTEXT.md`.
- **Quyết định kỹ thuật & lý do:** Schema-per-module + RLS tenant isolation (ADR-0027/0035); chỉ Approved mới được release ở mức DB constraint chứ không phải app code.
- **Bài học:** Trả lời hết open questions trước khi code (OQ-013 PII, OQ-006 RBAC) tránh phải đục lại giữa chừng.

## Tuần 3 (10/08 – 16/08): Build sprint lớn nhất

- **Đã làm:** 130+ commits trong 7 ngày: Alembic migrations 0001+, access control, registry, evaluation, release control, gateway `/v1`, call ledger qua RabbitMQ, worker không HTTP; ngày 15/08 chạy trọn bộ eval retrieval (14 file kết quả trong `eval/result/`, kịch bản S2–S10 trong `eval/evidence/versioning-matrix/`).
- **Khó khăn & giải pháp:** Test cần PostgreSQL + RabbitMQ thật (testcontainers) thay vì mock để đảm bảo tính chất broker; golden-live phải chạy theo file chứ không theo marker vì collection cả cây làm hỏng state DSPy LM.
- **Bài học:** "Two provisioning paths drift" — một đường setup duy nhất (testcontainers cho cả local lẫn CI) đỡ hơn nhiều về sau.

## Tuần 4 (17/08 – 23/08): Agent lớp trên, SDK và ổn định merge

- **Đã làm:** prompt-readiness + prompt-improvement (pre/post-publish agents) 20/08; Python SDK (`sdk/python`) + observation + migration skill 19/08; sửa conflict migration bị trùng revision ID sau merge (21/08); sửa hook AI-log SSL/auth và đẩy 155 entries lên phoenix (22/08).
- **Khó khăn & giải pháp:** Merge nhiều branch sinh duplicate alembic revision IDs → renumber lại chuỗi down_revision; `_pyrun.sh` chỉ biết venv Windows nên Mac fail SSL CERTIFICATE_VERIFY_FAILED → thêm nhánh `.venv/bin/python`.
- **Bài học:** Quy ước đặt tên migration phải được enforce sớm; script tiện ích dùng chung cần test trên mọi OS của thành viên.

## Tuần 5 (24/08 – 30/08): Deploy production & hoàn thiện deliverable *(đang cập nhật)*

- **Đã làm:** Deploy production lên https://prope.site — `healthz`/`readyz` xanh, `/api/*` và gateway `/v1/*` trả 401 đúng khi chưa xác thực; hoàn thiện bộ deliverable: `pitch-deck.pdf` 10 trang, `docs/evaluation.md`, `docs/worklog.md`, GIF demo giao diện và sơ đồ kiến trúc nhúng README.
- **Khó khăn & giải pháp:** 
- **Bài học:** 
