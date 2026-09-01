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

## Tuần 5 (24/08 – 30/08): Deploy production, tuần chỉnh UX & hoàn thiện deliverable

- **Đã làm:** Deploy production lên https://prope.site — `healthz`/`readyz` xanh, `/api/*` và gateway `/v1/*` trả 401 đúng khi chưa xác thực; hoàn thiện bộ deliverable: `pitch-deck.pdf` 10 trang, `docs/evaluation.md`, `docs/worklog.md`, GIF demo giao diện và sơ đồ kiến trúc nhúng README. Song song đó là tuần "polish" dày nhất về trải nghiệm người dùng (~60 commits): hàng loạt sửa lỗi UX theo phản hồi người dùng thật thu ngày 25/08 — hiển thị đúng refusal của provider trên mọi mặt lỗi, đặt tên provider trùng trong dialog đăng ký, adopt bảng giá model từ provider để số liệu chi phí không còn là ước lượng; thêm version pin gửi được thẳng từ SDK (27/08), chạy 2 uvicorn workers và nới healthcheck RabbitMQ lên 60s cho ổn định production (28/08); sửa đợt lỗi "ngược đời" trong luồng chat/draft/canonical (27/08) — assistant phủ nhận tool call mình vừa gọi, "keep as is" tự viết lại văn bản nó được yêu cầu giữ nguyên, folder đang chứa prompt báo là trống. Lý thuyết kiến trúc cũng được cập nhật theo code thật: atlas kiến trúc theo từng module + loại bỏ các diagram lỗi thời (31/08).
- **Khó khăn & giải pháp:** Phản hồi người dùng (mục 6 trong `docs/evaluation.md`) phơi ra khoảng cách giữa "hệ thống đúng" và "người dùng tin hệ thống đúng" — mock data ở Overview, PropAI thực thi action không có hiệu lực thật, chi phí lần gọi không nhìn thấy. Giải quyết bằng cách đi từng item một: mỗi phản hồi được chuyển thành commit sửa riêng, có thể kiểm chứng lại trên UI; những cái chưa sửa được (provider tạo muộn trong màn evaluation) được ghi nhận nguyên trạng trong `docs/user-feedback.md` thay vì xoá đi. Về vận hành: cache thông tin model/giá lấy từ provider cần cơ chế làm mới — chọn adopt giá do provider liệt kê thay vì bảng giá cứng trong code để không phải deploy mỗi khi provider đổi giá.
- **Bài học:** (1) Deploy sớm là đúng — một tuần chạy production thật tạo ra nhiều phát hiện hơn mọi buổi test nội bộ: refusal của provider chưa bao giờ được người dùng nhìn thấy cho tới khi có lỗi thật trên prope.site. (2) Thu phản hồi người dùng nguyên văn, kể cả tiêu cực, rồi map từng item vào commit sửa — đây là vòng lặp làm sản phẩm tiến bộ nhanh nhất trong cả 5 tuần. (3) Tài liệu kiến trúc cũng "hỏng" như code: khi code tiến nhanh 5 tuần liền, diagram không cập nhật trở thành nguồn thông tin sai — buộc phải có đợt "repoint diagram paths" cuối dự án.
