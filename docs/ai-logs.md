# AI Logs — Truy vết quá trình phát triển có AI hỗ trợ

> Bằng chứng quy trình xây dựng Prope có AI hỗ trợ và **được ghi vết đầy đủ**. Mọi phiên
> làm việc với AI agent (Claude Code, Codex, Copilot) đều đi qua hook `ai-log`:
> ghi local vào `.ai-log/session.jsonl` → git pre-push tự POST lên dashboard
> **https://phoenix.note.transformerlabs.ai/ai-logs** (đã đẩy 155 entries ngày 22/08).
> File này trích **10 trace đại diện** từ kho log thô; transcript đầy đủ từng phiên nằm trên dashboard.

## Thống kê kho log

> Kho log **đang sống** — pipeline ghi cả phiên đang chạy, nên số liệu dưới đây là ảnh
> chụp tại 25/08/2026 ~12:15 và sẽ tăng dần khi nhóm làm việc tiếp.

| Chỉ số | Giá trị |
|---|---|
| Tổng events | 370 (UserPromptSubmit 174 · Stop 120 · PostToolUse 76) |
| Số phiên (session, tính distinct) | 30 |
| Tool | Codex 258 · Claude Code 102 · Copilot 10 |
| Model | gpt-5.6-sol 198 · gpt-5.6-terra 60 · 112 event không ghi model (Copilot/Claude Code) |
| Phủ thời gian | 06/08 → 25/08/2026 (gần như toàn bộ giai đoạn build) |

Mỗi event mang: `ts`, `tool`, `event`, `session_id`, `model`, `repo`, `branch`,
`commit` (commit đang checkout khi gọi AI), `turn_id`, `prompt`. Email cá nhân
được lược bỏ trong tài liệu này; nội dung prompt sản phẩm không rời repo (A-020).

## 10 trace đại diện

Mỗi trace ghi: **Input** (prompt gửi cho agent, trích gốc có cắt bớt) → **Agent activity**
(công cụ/kỹ năng agent dùng) → **Outcome** (artifacts còn thấy được trong repo — kiểm chứng
được bằng git, không phải lời khai).

### Trace 1 — Phân tích nghiệp vụ bằng chuỗi skill (06/08)

- **Phiên:** `019fd687` · Codex · gpt-5.6-terra
- **Input:**
  > Use the installed hybrid Business Analysis workflow. First inspect the entire
  > repository without modifying source code. Then use these skills in order:
  > 1. $business-problem-framing  2. $stakeholder-analysis  3. $as-is-p…
- **Agent activity:** chạy tuần tự các skill phân tích nghiệp vụ sau khi đọc toàn repo.
- **Outcome:** `docs/business-analysis.md` (commit "add business-analysis.md") — nền tảng
  problem statement "0/11 đội có approval step" dùng trong pitch deck.

### Trace 2 — Audit gap yêu cầu Gate G2 (07/08)

- **Phiên:** `019fda18` · Codex · gpt-5.6-terra
- **Input:**
  > $requirements-gap-auditor Kiểm tra repo hiện tại so với các deliverable của Gate G2
  > và liệt kê những công việc còn thiếu.🎯 Gate G2 — MVP: Là agent có thể nhận input →
  > xử lý → trả output có ý nghĩa cho ít nhất 1 user flow…
- **Agent activity:** skill audit đối chiếu repo với tiêu chí gate, liệt kê gap.
- **Outcome:** danh sách việc thiếu làm đầu vào cho sprint tuần 3 (130+ commits).

### Trace 3 — Trích "visual DNA" từ moodboard thành design system (07–08/08)

- **Phiên:** `019fda18` / `019fdf3d` · Codex · gpt-5.6-terra
- **Input:**
  > $vibe-to-ui — Phân tích các ảnh trong thư mục moodboard.png: 1. Trích xuất visual DNA,
  > màu sắc, typography, layout, spacing, imagery và motion. 2. Tạo 3 design direction…
- **Agent activity:** skill phân tích ảnh → sinh design tokens.
- **Outcome:** bộ design token của Prope (primary `#17444C`, secondary `#7FACC7`, accent
  `#FFD42A`…) — chính là nội dung file `tokens.json` trong repo hôm nay.

### Trace 4 — Dựng lại user flow UX từ bằng chứng repo (08/08)

- **Phiên:** `019fe03d` · Codex · gpt-5.6-terra/sol
- **Input:**
  > Use $user-flow-diagram. Read these two files completely before generating anything:
  > `business-analysis.md`, `prope_source_of_truth.md`. Your task is to reconstruct the
  > product's USER FLOW for UI/UX design…
- **Agent activity:** đọc bằng chứng repo → vẽ Mermaid flow → sửa lỗi 5/9 file render
  không được ("file 2, 4, 6, 8, 9 đang bị lỗi… kiểm tra xem có phải do skill không").
- **Outcome:** `docs/user-flows/*.mmd` (overview, authentication, prompt-management,
  evaluation, review-approval…) dùng làm bản thiết kế UI.

### Trace 5 — Quyết định sản phẩm: tách luồng lưu prompt và luồng đánh giá (10/08)

- **Phiên:** `019fe597` · Codex · gpt-5.6-sol
- **Input:**
  > tôi muốn tách luồng evaluation và luồng save prompt riêng, tức là khi add prompt thì
  > save vào để lưu prompt, không cần gửi để đánh giá, phânf evaluation nó sẽ thay cho
  > xem diff (tức là khi đánh giá thì chắc chắn xem diff được)
- **Agent activity:** phiên này bắt đầu bằng ASCII user flow theo góc nhìn UI/UX, rồi
  dựng prototype HTML tương tác có mock, tối ưu luồng theo mẫu PromptLayer — mỗi vòng
  đều qua chất vấn "vẽ lại chi tiết theo cái quay lại vòng chỉnh sửa sẽ nối vào đâu"
  trước khi chốt quyết định tách luồng ở trên.
- **Outcome:** cấu trúc FE cuối cùng tách rõ hai luồng trong
  `src/prope-fe/features/prompt-lifecycle/`: lưu prompt (`NewPromptComposer.tsx`,
  `PromptEditorPage.tsx`) khác đánh giá (`EvalRunPage.tsx`, `DatasetPage.tsx`,
  `ReviewQueuePage.tsx`) — đánh giá luôn kèm xem diff, đúng như yêu cầu.

### Trace 6 — Figma MCP: design → code component Navigation (09/08)

- **Phiên:** `019fe531` / `019fe597` · Codex · gpt-5.6-terra/sol
- **Input:**
  > Use only the standalone MCP server named `figma`. Call `figma.get_design_context`
  > for: fileKey=dVGYJ8lWqkx5gSX5PBLa9e nodeId=159:495 skillNames=figma-design-to-code
- **Agent activity:** gọi MCP tool lấy design context từ file Figma "🌍 Prope — Prompt as
  a property", chuyển thành HTML component, rồi sửa code FE dựa trên đó.
- **Outcome:** `docs/ui-component/component-as-html/navigation-bar.html` + Navigation
  trong `src/prope-fe`.

### Trace 7 — Khung frontend với mock data ở tầng TanStack (10–11/08)

- **Phiên:** `019fea11` · Codex · gpt-5.6-sol
- **Input:**
  > Create a FE structure folder in /src based on techstack from /docs/brainstorm.
  > BE not implemented yet, mockup UI only… return mock data at Tanstack level so that
  > I can replace with real endpoint easier later
- **Agent activity:** sinh khung thư mục đúng convention (`components/ui`, `features/<name>`),
  sau 2 vòng chỉnh sửa theo phản hồi.
- **Outcome:** skeleton `src/prope-fe` — về sau đổ UI thật vào đúng các slot này.

### Trace 8 — Vòng sửa UI qua browser comments (16/08)

- **Phiên:** `01a00a3e` · Codex · gpt-5.6-sol
- **Input:**
  > # Browser comments — ## User Comment 1 — File: browser:EDIT WITH PROPE AI —
  > Node position: (610, 137)… Page URL: http://localhost:5173/ap…
- **Agent activity:** nhận comment đánh dấu trực tiếp trên trang đang chạy (vị trí node,
  URL) → sửa đúng component được chỉ → xác nhận trên trình duyệt.
- **Outcome:** các màn Overview/PropeAI/Import chỉnh theo feedback — chính là luồng
  xuất hiện trong video demo.

### Trace 9 — Plan → implement → verify: notification FE (20–21/08)

- **Phiên:** `01a01da1` / `01a01ff9` / `01a02218` · Codex · gpt-5.6-sol/terra
- **Input:**
  > Tôi chỉ muốn thay đổi FE và sử dụng TanStack, hãy đọc AGENTS.md
  > → PLEASE IMPLEMENT THIS PLAN: # Notification Frontend bằng TanStack Query — Chỉ thay
  > đổi `src/prope-fe`; không thêm backend, database, API hay SSE…
  > → Kiểm tra xem fe và be của notification đã nối vào nhau chưa, **chỉ kiểm tra thôi nhé**
- **Agent activity:** ba turn tách bạch vai trò — đọc ràng buộc (AGENTS.md), implement
  theo plan đã duyệt, rồi một turn **chỉ đọc để verify** không sửa code.
- **Outcome:** notification FE nối BE, đúng phạm vi "chỉ FE" như plan.

### Trace 10 — Dựng khu Cài đặt: FE-only, test với BE thật, sửa theo comment trên trang (19–20/08)

- **Phiên:** `01a01a64` · Codex · gpt-5.6-sol
- **Input:**
  > tôi chỉ muốn sửa FE nhưng muốn test với BE hiện tại (sửa giao diện thôi)
  > …
  > Tôi muốn taskbar của cài đặt sẽ nằm bên trái, khi chọn nút cài đặt thì sidebar sẽ
  > tự động swap sang cái sidebar của phần cài đặt. *(browser comment tại
  > `localhost:5173/app/settings/keys`, kèm toạ độ node + screenshot)*
- **Agent activity:** thiết lập chạy FE dev nối thẳng BE đang chạy (không cần dựng
  lại Docker cho việc sửa giao diện), rồi nhận chuỗi comment đánh dấu trực tiếp trên
  trang — API key nhà cung cấp, Thành viên, Thông tin cá nhân, ngôn ngữ — sửa đúng
  component được chỉ từng vòng.
- **Outcome:** khu Cài đặt hoàn chỉnh trong `src/prope-fe/features/account/`
  (`SettingsPage.tsx`, `ProfilePage.tsx`, `AccountPage.tsx`) — nơi cấu hình consumer
  API key và provider credential của sản phẩm hôm nay.

## Phân biệt hai loại trace AI của Prope

| | Trace **quá trình xây dựng** (file này) | Trace **runtime sản phẩm** |
|---|---|---|
| AI nào | Claude Code, Codex, Copilot hỗ trợ nhóm dev | App Agent của Prope (conversion, PropeAI, chat, dataset drafting) |
| Ghi ở đâu | `.ai-log/*.jsonl` → dashboard phoenix | Call Ledger + Log & Trace trong app; Langfuse tuỳ chọn |
| Xem bằng chứng | Bảng trên + dashboard phoenix | `GET /api/v1/eval-runs/{run_id}/cases/{case_result_id}/trace`, màn Overview → Log & Trace |

Trace runtime có đủ input → LLM call → retrieval → output (Chat Orchestrator là luồng
có RAG retrieval); xem `docs/evaluation.md` mục 5 cho span Langfuse khi bật.
