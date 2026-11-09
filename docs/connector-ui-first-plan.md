# Connector thao tác trực tiếp trong VS Code

Yêu cầu: panel cạnh chat Codex, dán prompt và thực hiện toàn bộ lưu, dataset,
evaluation, cải tiến và so sánh bằng nút bấm. MCP là tùy chọn, không phải điều kiện
để sử dụng panel. Không đọc tự động chat, không approve/release, không thêm framework.

## Rủi ro và quyết định

- Tách đề xuất do người dùng nhập khỏi quyền đọc folder đã ghép nối MCP. Session
  và quyền backend là authority; không giả lập grant MCP cho thao tác UI.
- Credential ở extension host. Chỉ thêm thao tác có schema và endpoint xác định,
  không mở proxy HTTP ghi tổng quát.
- Tái sử dụng API và component dataset/eval/agent-run hiện có. Không dùng
  draftApi hay hook tạo draft giả trong frontend.
- Cải tiến dùng provider/backend Prope, không tự gửi lệnh vào chat Codex.
- Request tốn phí cần xác nhận, không retry ghi không rõ kết quả; candidate được
  xem diff và chỉ lưu revision sau xác nhận. So sánh giữ cùng dataset/config.

## Phase 1: nhập prompt và lưu không cần MCP

Scope/files: contracts, extension host, Proposals, ConnectorPanel, form nhập mới,
locale vi/en. Thêm nguồn UI theo session, chọn folder, dán prompt, tái sử dụng
conversion/diff/save. Thêm mở prompt đã lưu để tiếp tục sau khi mở lại panel.
Test: pytest tạm cho schema, nguồn UI/MCP isolation, hết session, preview/save
không tự ghi. Acceptance: đăng nhập rồi dán/lưu được, không cần adapter hay pairing.

## Phase 2: dataset và evaluation trong panel

Scope/files: host actions/allowlist, connector API, các component dataset và eval.
Tái sử dụng dataset editor, API attachment, run console; chạy original riêng và
so sánh hai revision bằng API hiện có, đọc lịch sử để mở lại run.
Test: pytest tạm cho endpoint/body allowlist, xác nhận chi phí, version/prompt
ownership và không replay; tsc/lint/build. Acceptance: không mở browser để tạo/gắn
dataset hoặc chạy/đọc eval.

## Phase 3: cải tiến và nghiệm thu

Scope/files: host action agent-run, connector improvement UI, docs/build.
Chọn eval evidence, gọi improvement agent-run thật, hiển thị trạng thái và
candidate; tạo đề xuất nội bộ để review diff/save revision, không mock draft.
Test: pytest tạm cho evidence/target/status/generation isolation; toàn bộ gates
backend/SPA/extension, VSIX, Docker rebuild/health; người dùng xác nhận native
khi nghiệm thu thao tác thật. Không UI/e2e runner. Xóa test tạm sau pass.
Acceptance: dán → lưu → dataset → eval → cải tiến → diff → lưu candidate → so sánh
hoàn tất trong panel; không bắt buộc chat hoặc ghép nối MCP.
