# VS Code connector v1

The connector captures only chat content explicitly submitted by an agent and
confirmed by the user. It never reads another extension's private chat storage.

| Phase | Scope and files | Implementation | Checks / acceptance |
| --- | --- | --- | --- |
| 1 | `integrations/vscode`, frontend connector entry / API transport | Local sign-in, workspace, credential-free Webview | Session-local pytest for transport and boundaries; real API data |
| 2 | Extension broker, stdio adapter, chat skill | Pairing, scoped reads, in-memory proposals, explicit save | MCP subprocess checks; no write before human confirmation |
| 3 | Evaluation schemas/API and connector UI | Explicit original/candidate runs on one dataset suite | Pytest for permissions, transaction, equivalent configuration, failures |
| 4 | Packaging, documentation, evidence feedback | Bundled VSIX, audit-safe logs, candidate loop | Typecheck/lint/build, Docker rebuild/health; host acceptance by user |

No release/approval tools, automatic collection, repo scanning, remote backends,
new optimizer. Backend permissions and RLS remain the
authority. Prompt bodies and credentials must never enter logs. Tests created
for this implementation are temporary; existing repository tests are preserved.

Implementation finding: Draft content can be overwritten in place. Migration
0057 adds an immutable, private evaluation input snapshot for explicit pairs so
later Draft edits cannot change what the worker measures. Existing run paths
retain their behavior and snapshots are never returned in management responses.

## Kiểm tra Codex thật ngày 2026-10-30

Đã cài VSIX vào VS Code thật và mở panel trong cửa sổ test riêng. Client thử là
Codex app-server 0.157.1, dùng MCP stdio đã đóng gói; không mock model hoặc broker.
Model `gpt-6.1-sol` trong cấu hình máy bị tài khoản từ chối trước khi gọi MCP;
phiên thử dùng riêng `gpt-6-sol`, không sửa model mặc định của người dùng.

Phát hiện và sửa lỗi 401: polling khi chưa đăng nhập luôn gọi invalidation, tạo
vòng lặp tải lại panel và thu hồi mã ghép nối. Phản hồi 401 về chậm còn có thể xóa
session vừa đăng nhập. Request hiện ghi nhận cookie lúc gửi và chỉ invalidation
khi chính session đó vẫn còn hiện hành. Năm kiểm tra pytest tạm bao phủ anonymous,
401 đồng thời, 401 cũ sau login và logout; trước sửa có bốn ca fail, sau sửa cả năm
pass. Đã sửa thêm các bản dịch xác nhận native tiếng Việt bị mất dấu.

Khi Draft gốc được sửa ngoài panel, form candidate từng giữ model cũ trong
default values dù API đã trả binding mới. Form hiện chờ đọc xong revision và tạo
lại trạng thái form/preview khi dữ liệu revision thay đổi. Một lỗi khác làm adapter
bỏ token sau heartbeat 502/503 tạm thời đã được sửa: chỉ 401 hoặc lease hết hạn mới
yêu cầu ghép nối lại. Hai ca pytest subprocess MCP kiểm tra lỗi tạm thời và 401;
toàn bộ bảy ca hồi quy của phiên kiểm tra đều pass. Không chạy UI test runner.

Người dùng đã đăng nhập/chọn workspace và xác nhận ghép nối. Codex gửi nguyên văn
prompt tiếng Việt tổng hợp, nhận `awaiting_confirmation`; người dùng thấy và đóng
đề xuất. Codex đọc lại danh sách đề xuất rỗng. Log backend ghi nhận không có request
ghi registry hoặc conversion trong nhánh capture rồi đóng đề xuất.

Sau xác nhận của người dùng, conversion trả 200; tạo prompt và revision đều trả
201. Prompt thử là `prm_01M65S5S5N3DJJ5VR3CD8G1TXV`, original revision là
`rev_01M65S5SABDH1S8TVSADG2F9G5`. Codex đọc lại revision qua MCP và nguyên bản giữ
đúng Unicode tiếng Việt. Candidate đã được người dùng lưu thành revision
`rev_01M65TCCJ5PYHHGRJ61T60V42H`. Sau khi người dùng sửa model ID nhập nhầm, hai
revision cùng dùng provider `prv_01M5P2SB156MM17W73GMMW8G56`, model
`gemini-2.5-flash-lite`, parameters `{}`.

Cặp evaluation thật dùng dataset `builtin:bien-chua-thay-the@1`, suite snapshot
`evs_01M65TF46SH5G464TV06DQ0Z06`:

| Vai trò | Run ID | Trạng thái | Pass / fail / error | Input / output token |
| --- | --- | --- | --- | --- |
| Original | `evr_01M65TF47DAPA1W04HXH7H8RXB` | completed | 5 / 0 / 0 | 327 / 35 |
| Candidate | `evr_01M65TF47PT0XS8AF16175GG8X` | completed | 5 / 0 / 0 | 462 / 35 |

Sau khi mở lại cửa sổ và người dùng xác nhận ghép nối lại, Codex gọi thành công
`prope_get_revision` cho cả hai revision và `prope_get_evaluation` cho đúng cặp run.
Response xác nhận `comparable: true`, `metric_kind: deterministic`, cùng cấu hình;
cả mười case có output `PROPE_CONNECTOR_OK`. Chi phí và currency là null, không
được hiểu là miễn phí. Bộ builtin kiểm tra biến chưa thay thế bằng regex, chưa đủ
để kết luận candidate tốt hơn hoặc đại diện đầy đủ cho chất lượng prompt.

Luồng đã kiểm chứng: capture tiếng Việt → đóng đề xuất không ghi → xác nhận lưu
original → candidate gắn đúng baseline → xác nhận lưu candidate → worker chạy cặp
run cùng suite → Codex đọc evidence qua MCP. Đây là Codex app-server thật với panel
VS Code thật; chưa nghiệm thu giao diện chat của extension Codex hoặc Claude Code.
`prope_prepare_evaluation` chưa được gọi trực tiếp từ Codex trong lượt live này;
đề xuất/chạy evaluation đã đi qua panel.

Một lần Codex báo `usageLimitExceeded` sau khi đã gửi candidate thành công. Sau
mốc reset được client báo, lượt đọc evidence bằng Codex đã hoàn tất. Không đổi
quota, không đổi tài khoản hoặc cấu hình model mặc định để xử lý lỗi này.

Backend Ruff, SPA type-check/lint/build và extension type-check/lint/package đều
pass; VSIX đã cài vào VS Code. Còn warning bundle SPA lớn hơn 500 kB đã tồn tại.
Các file pytest và harness hồi quy tạm của lượt kiểm tra đã được xóa.
Sau lượt rebuild/restart cuối, health/readiness đều 200 và Codex gọi lại
`prope_connection_status` vẫn nhận `connected: true`. Client Codex thử đã được dừng
và script client tạm đã được xóa; revision và run đã lưu được giữ nguyên.

Rollback connector và lưu ý giữ snapshot evaluation được ghi trong
[README của extension](../integrations/vscode/README.md#kiểm-chứng-và-rollback).
Lượt live test không sửa cấu hình model/MCP toàn cục, không thêm migration mới,
không approve hoặc release prompt.
