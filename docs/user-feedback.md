# User Feedback — Prope

> Feedback người dùng thật sau khi dùng sản phẩm, thu ngày **25/08/2026**. Ghi nhận
> **nguyên văn, không tô hồng** — phản hồi tiêu cực là một phần của bằng chứng, vì nó
> chỉ đúng chỗ sản phẩm chưa đạt promise.

## Bảng feedback

| # | Feedback (nguyên văn) | Phân loại | Mức ảnh hưởng |
|---|---|---|---|
| F-01 | "Dữ liệu tổng quan hiện tại chỉ là mock Data." | Thiếu chức năng / dữ liệu | Cao — ảnh hưởng độ tin cậy của màn Overview |
| F-02 | "PropAI: một số tác vụ còn đang xử lý sai, ví dụ yêu cầu thêm prompt vào Folder khác, PropAI xác nhận nhưng prompt mới vẫn chỉ được lưu mặc định ở Folder Imported (Folder mặc định khi thêm prompt không yêu cầu Folder)." | Bug agent (HITL action không có hiệu lực thật) | Cao — đúng luồng PropeAI được demo |
| F-03 | "UI phần tổng quan không gian đang khá bị lệch, không thẳng hàng." | Bug UI/UX | Trung bình |
| F-04 | "Chưa đo được chi phí của các lần gọi." | Thiếu chức năng nhìn thấy được (cost visibility) | Cao — ROI là một trong hai promise chính |
| F-05 | "Trong màn đánh giá, nếu thêm provider trong màn này (trường hợp mà quên thêm provider ở màn Soạn prompt), thì hệ thống không nhận." | Bug luồng (provider tạo muộn không được nhận) | Trung bình — chặn người mới lần đầu chạy eval |

## Người phản hồi

Checklist BTC đếm theo **số người** (3–5 người) — 5 mục feedback trên đến từ 5 mentor
đã dùng app thật:

| # | Người phản hồi | Role |
|---|---|---|
| F-01 | Lưu Trọng Hiếu | Mentor |
| F-02 | Trần Thành Trung | Mentor |
| F-03 | Phạm Minh Hiếu | Mentor |
| F-04 | Ngô Đình Luân | Mentor |
| F-05 | Phạm Văn Ngoan | Mentor |

## Phân loại đề xuất (nhóm xác nhận trước khi đưa vào backlog)

- **F-01 + F-04 có thể cùng một gốc:** call ledger đã có bảng giá effective-dated và
  tổng spend ở tầng backend (`docs/architecture.md` — "Call Ledger: call metadata,
  bảng giá effective-dated và tổng spend"); nếu Overview đang render mock data thì
  chi phí "chưa đo được" có thể là *chưa được nối UI* chứ không phải *không có đo*.
  Cần xác nhận phạm vi: màn nào đang mock, màn nào đọc API thật.
- **F-02:** hành vi đúng phải là pending action của Chat Orchestrator thực thi thật
  (đổi folder) sau khi người dùng xác nhận — xác nhận lại `POST /chat/actions/{action_id}`
  có được gọi và có đổi được `folder` của prompt không.
- **F-05:** provider tạo trong màn evaluation không được nhận — kiểm tra danh sách
  provider được load lại sau khi tạo (cache/stale state ở FE).

## Trạng thái xử lý

| # | Trạng thái | Fix ở |
|---|---|---|
| F-01 → F-05 | **Mới ghi nhận** (25/08/2026) — chưa gán người xử lý | — |
