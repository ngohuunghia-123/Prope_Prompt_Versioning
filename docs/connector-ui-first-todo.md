# Tiến độ

- [x] Phase 1: nhập/lưu và mở lại prompt trực tiếp
- [x] Phase 2: dataset, eval đơn và so sánh trong panel
- [x] Phase 3: improvement thật, diff/save, docs và gates
- [ ] Nghiệm thu panel sau reload bằng thao tác người dùng; xác nhận native cho bước ghi/tốn phí

36 ca pytest tạm pass: UI/MCP owner isolation, schema/allowlist, Unicode,
canonical preview không gọi provider, target/evidence, duplicate submission,
session đổi trước/sau request, xác nhận bị hủy, kết quả ghi chưa rõ và gate từ chối.
Ruff backend, SPA type-check/lint/build, extension type-check/lint/package pass.
Còn warning bundle SPA lớn có từ trước. VSIX cài tại VS Code; Docker rebuild xong,
health/readiness đều 200. Installed extension host khớp bundle đã build.
Không chạy UI/e2e runner và không gọi provider/evaluation thay người dùng.
Các file pytest, driver và bundle fixture tạm đã được xóa sau khi pass.

## Sửa mở revision và đánh giá đơn

- Scope: mở prompt có một revision và chạy riêng revision đó, không cần candidate.
- Files: `OpenRevisionForm`, `useOpenRevisionForm`, `EvaluationComposer`, locale vi/en;
  `DirectActions`; schema `EvalRunStart` và helper `_run_handles` cùng hai caller.
- Implementation: tự chọn bản duy nhất; chặn mở khi tải/lỗi/ID không hợp lệ;
  tab So sánh giải thích khi chưa đủ hai bản. Connector tắt released baseline bằng
  `include_released_baseline=false`; caller cũ giữ mặc định `true`.
- Tests: 12 ca pytest logic tạm pass, gồm chọn revision, loading/error/empty/stale,
  hủy xác nhận, request eval đơn và baseline cũ. Không chạy UI/e2e hay provider thật.
  File test/driver/bundle tạm đã xóa; lint/type-check/build/package đều pass.
- Acceptance tự động đạt: bản duy nhất được chọn; eval đơn không đọc/chạy baseline;
  API cũ không đổi mặc định. VSIX đã cài, host và panel khớp bundle đã build.
  Docker rebuild/restart thành công; `/healthz` và `/readyz` trả 200; container
  app xác nhận schema hỗ trợ cờ baseline và mặc định vẫn là `true`.
- Cần nghiệm thu thủ công sau **Developer: Reload Window**: chọn prompt một revision,
  mở workspace, gắn dataset và xác nhận chạy trong tab Đánh giá khi muốn phát sinh chi phí.

## Tab So sánh nội dung

- Scope: thay form evaluation trong tab So sánh bằng diff nội dung, không cần dataset.
- Files: `RevisionWorkspace`, `RevisionContentComparison`, `useRevisionContentComparison`,
  locale vi/en và README extension. Không đổi API backend hay quyền MCP.
- Implementation: đọc hai revision thuộc cùng prompt, chọn canonical/nguyên bản;
  tái sử dụng `PromptBlockAccordion`, giữ thẻ XML/thứ tự block dưới dạng source;
  hỗ trợ chỉ hiện thay đổi và thông báo nội dung giống nhau. Không có mutation,
  dataset request, provider call hay eval run trong tab này.
- Tests: 14 ca pytest logic tạm pass: mặc định/chọn thủ công, cùng revision,
  loading/error/empty/stale, sai prompt/ID response, nguyên bản, XML đổi thứ tự,
  không nối tab với evaluation/write tool và locale keys. Không dùng UI/e2e runner.
  File test/driver/bundle tạm đã xóa. Ruff, SPA type-check/lint/build và extension
  type-check/lint/package pass; VSIX đã cài và panel khớp bundle. Docker rebuild
  thành công, health/readiness trả 200. Cảnh báo bundle SPA lớn có từ trước.
- Acceptance: diff chỉ cần hai revision; thiếu hai bản thì giải thích; đánh giá riêng
  vẫn ở tab Đánh giá, đối chiếu chất lượng bằng dataset vẫn qua MCP có xác nhận.
- Nghiệm thu trực tiếp trong VS Code sau reload vẫn cần người dùng thực hiện.

## Tương phản chữ trên nút primary

- Scope/files: token chữ riêng trong `theme.css`, dùng ở `buttonVariants` và
  ba entry SPA/panel/navigation-preview. Không sửa `styles.css`.
- Implementation: chữ xanh đậm trên nền vàng trong cả theme sáng/tối; áp dụng
  qua primitive Button dùng chung, giữ các trạng thái disabled và loading.
- Tests: 8 ca pytest tạm pass: tương phản >= 7:1 ở 6 tổ hợp theme/trạng thái
  (thường/hover/loading), token và utility có trong CSS build SPA/panel.
  Đã xóa file test tạm; không chạy UI/e2e runner.
- Gates: Ruff, SPA type-check/lint/build, extension type-check/lint/package pass;
  VSIX cài thành công, CSS panel khớp bản build. Docker rebuild thành công,
  health/readiness 200. Cảnh báo bundle SPA lớn có từ trước.
- Acceptance: màu đã kiểm tra bằng tính toán và CSS build; cần reload VS Code
  để xem trực tiếp nút với extension mới.

## Font tiêu đề trong panel offline

- Scope/files: `connector-theme.css` và entry Webview. Rà tất cả tiêu đề connector
  cùng thành phần tái sử dụng; chúng dùng token `--font-display` hoặc quy tắc h1–h6.
- Implementation: dùng `--vscode-font-family` cho body/tiêu đề, fallback Segoe UI;
  code/XML dùng font monospace của editor. Không cần tải Fraunces/Manrope;
  không đổi typography của SPA, không sửa `styles.css`.
- Tests: 6 ca pytest cấu hình/CSS build pass: thứ tự override, font h1–h6 và
  utility, monospace, không tải font qua mạng, phạm vi Webview, hai chuỗi tiếng Việt
  hợp lệ Unicode. Đã xóa test tạm; không chạy UI/e2e runner.
- Gates: Ruff, SPA type-check/lint/build, extension type-check/lint/package pass;
  VSIX đã cài, CSS bản cài khớp bản build. Docker rebuild thành công;
  health/readiness 200. Cảnh báo bundle SPA lớn có từ trước.
- Acceptance trực tiếp: reload VS Code rồi kiểm tra tiêu đề và dấu tiếng Việt;
  chưa xác minh bằng quan sát giao diện sau reload trong phiên này.

## Ghép nối từ giao diện, không lấy mã qua chat

### Phase 1 — Đăng ký từ adapter và giữ ranh giới quyền

- Scope/files: `mcp-stdio.ts`, `broker.ts`.
- Implementation: MCP initialized đăng ký client chờ với metadata name/version;
  poll 5 giây để nhận token sau xác nhận. Chỉ một yêu cầu authorize cùng lúc;
  hết hạn/revoke thì đăng ký lại, không tự cấp quyền. Broker validate metadata,
  kiểm tra lại request còn sống sau khi đọc session để chặn revoke/approve race.
- Tests/acceptance: SDK MCP client thực chạy adapter subprocess tự đăng ký trước
  mọi tool call và không đọc session backend khi chưa cấp quyền. Scope, token
  memory, lease, explicit human confirmation và giới hạn pending được giữ lại.

### Phase 2 — Chọn client trong VS Code và nghiệm thu

- Scope/files: `extension.ts`, locale native vi/en, hướng dẫn trong panel,
  locale connector vi/en, README và skill chat.
- Implementation: QuickPick client đang chờ thay cho nhập mã, chọn folder rồi
  modal xác nhận. Tên/phiên bản tự khai báo và được loại ký tự điều khiển/codicon;
  không coi metadata là chứng thực. Không có ticket/token trong mục UI.
- Tests: 17 ca pytest tạm pass, gồm stdio initialize không gọi tool, tự nhận quyền,
  chưa cấp quyền, sai scope, lỗi tạm, revoke, expired, thiếu workspace, đổi mật khẩu,
  metadata sai, Origin lạ, concurrent approval và revoke trong lúc chờ session;
  native confirmation/locale checks. Backend API là fixture; không cấp quyền phiên
  Prope thật hoặc chạy tác vụ ghi/tốn phí. Không chạy UI/e2e runner.
- Acceptance trực tiếp còn lại: reload VS Code, restart MCP trong host đã cấu hình,
  bấm Ghép nối agent, chọn client/folder rồi tự xác nhận. Không cần chat hay nhập mã.
- Gates: Ruff, SPA type-check/lint/build và extension type-check/lint/build/package
  pass. File pytest/driver/endpoint fixture đã xóa; VSIX cài thành công, adapter/host
  khớp bundle đã build. Docker rebuild thành công, health/readiness 200.
  Cảnh báo bundle SPA lớn có từ trước; chưa nghiệm thu hộp thoại trong Codex/Claude thật.

## Kiểm tra kết nối ngay trong extension

- Phase 1 — scope/files: `broker.ts`, `mcp-stdio.ts`, dispatcher extension và
  contracts/API connector. Danh sách chỉ trả ID công khai/name/status/folder/heartbeat,
  không trả ticket/token; kiểm tra session/workspace trước khi đọc hoặc test.
  Adapter gửi heartbeat đầu tiên sau khi nhận quyền. Nút check phải chờ một
  heartbeat mới (tối đa 25 giây), không dùng trạng thái đã cấp quyền làm bằng chứng.
- Phase 2 — scope/files: `AgentConnections`, `ConnectorPanel`, locale vi/en và README.
  Danh sách client có loading/empty/error/success; trạng thái chờ cấp quyền,
  đã cấp quyền/chờ adapter và đã nhận heartbeat. Kiểm tra bằng nút, không có chat
  hay MCP tool call của model; timeout có hướng dẫn. Đóng khu vực kết nối dừng polling.
- Acceptance: người dùng ghép nối/chọn folder/xác nhận và kiểm tra heartbeat hoàn toàn
  bằng giao diện; prompt/eval/cải tiến vẫn dùng các tab hiện có. Không thêm quyền
  approve/release, không tự cấp quyền, không tự chạy tác vụ tốn phí. Kiểm tra
  adapter–broker/session không chứng minh model đã gọi tool hay chất lượng prompt.
- Tests: 16 ca pytest tạm pass: SDK MCP thật/adapter subprocess tự kết nối và trả
  heartbeat mới không gọi tool, snapshot ba trạng thái không lộ ticket/token,
  pending không có quyền, heartbeat cũ/timeout, revoke/lease expiry, đổi session,
  payload sai và locale. Backend là fixture, không cấp quyền hoặc ghi phiên Prope thật.
  Test/driver/endpoint tạm đã xóa; không chạy UI/e2e runner.
- Gates: Ruff, SPA type-check/lint/build, extension type-check/lint/build/package
  pass. VSIX đã cài, host/adapter khớp bản build; Docker rebuild thành công,
  health/readiness 200. Cảnh báo bundle SPA lớn có từ trước. Cần nghiệm thu giao diện
  thực sau reload và nạp lại MCP; không tự bấm xác nhận cấp quyền của người dùng.

## Nhận diện cuộc chat sử dụng MCP

- Yêu cầu đã chốt: nhận diện thread thực sự gọi MCP, không suy đoán tab chat đang mở.
- Phase 1 — kiểm chứng nguồn ID: Codex app-server cài trên máy
  `0.164.0-alpha.11.1` gửi `_meta.threadId` theo thread trong `mcpServer/tool/call`.
  Kiểm chứng bằng hai thread ephemeral và MCP fixture, không gọi `turn/start`,
  không gọi model/provider, không đọc lịch sử chat thật. Handshake/heartbeat
  không có thread ID; `CODEX_THREAD_ID` không có trong MCP subprocess thử nghiệm.
- Phase 2 — scope/files: contracts connector, adapter, broker, native picker,
  `ConnectionConversations`, agent list, locale vi/en và README. Adapter chỉ đọc
  `_meta.threadId`; không lấy tool arguments/environment/prompt body làm identity.
  `/pair/observe` yêu cầu ticket riêng của adapter, chỉ thêm metadata trong bộ nhớ,
  không cấp quyền. Mỗi kết nối giữ tối đa 32 thread với first/last seen và nguồn.
  UI hiển thị ID riêng từng thread, unknown khi thiếu metadata, không gán tên chat.
- Tests: 15 ca pytest tạm pass, gồm hai ID thực khớp thread do Codex tạo,
  không gọi model, missing metadata, giả ID qua arguments, metadata sai, nhiều
  thread/kết nối, ticket/expiry/isolation, cập nhật thời điểm, giới hạn bộ nhớ,
  revoke, không lộ token/ticket và locale. Backend Prope là fixture; không cấp
  quyền phiên Prope thật, không chạy UI/e2e runner.
- Acceptance: panel nhận diện ID của lời gọi host đã quan sát; không có chứng thực
  chống tiến trình local giả mạo, không đọc transcript/title hay đổi quyền theo thread.
  Host không gửi `threadId` vẫn unknown; quyền đọc tiếp tục theo kết nối/folder.
- Gates: Ruff, SPA type-check/lint/build, extension type-check/lint/build/package
  pass, native locale parity pass. VSIX đã cài, host/adapter khớp build; Docker
  rebuild thành công, health/readiness 200. Đã xóa toàn bộ fixture/test/schema/
  CODEX_HOME tạm của chẩn đoán; không đổi cấu hình Codex thật hoặc thêm hook.
  Cảnh báo bundle SPA lớn có từ trước. Chưa nghiệm thu panel trực tiếp sau reload.

## Tên cuộc trò chuyện từ Codex

- Phase 1 — kiểm chứng API: OpenAI App Server docs và schema của Codex cài trên
  máy xác nhận `thread/read` trả `thread.name`, `includeTurns=false` chỉ metadata.
  Tạo một thread/tên tiếng Việt trong CODEX_HOME fixture; app-server khác đọc lại
  được đúng tên, không resume hoặc gọi model.
- Phase 2 — scope/files: `codexThreadTitle.ts`, guard broker, dispatcher extension,
  contracts/API connector, `ConversationIdentityCard`, component danh sách và locale.
  Nút Lấy tên/Cập nhật đọc metadata theo đúng ID đã quan sát trên kết nối Codex
  đã duyệt, kiểm tra lại session/connection sau đọc; không quét lịch sử hoặc dùng
  preview làm tên. Tên null/thiếu và lỗi đọc có trạng thái riêng. ID là thông tin phụ.
  RPC dùng spawn không shell, windowsHide, timeout/giới hạn output/concurrency;
  chỉ whitelist tên/ID/source/timestamp sang Webview. Log request/connection/status/
  latency, không có tên, prompt, error message Codex hay credential.
- Tests: 18 ca pytest tạm pass: metadata tên thật/Unicode từ Codex cài trên máy,
  RPC chỉ initialize/read(false), UTF-8 split, không preview fallback, response sai/
  khác thread/malformed/error/process exit, output cap/timeout/concurrency, scope
  trước khi cấp quyền/ID chưa quan sát/host khác, revoke và session change khi đang
  chờ, target schema và locale. Không gọi model/provider, không dùng UI/e2e runner.
- Acceptance: tên thật từ API là dòng chính; chưa lấy/không trả tên/lỗi phải rõ;
  người dùng không cần chat hay đặt tên thủ công. Giới hạn Codex local có dữ liệu
  thread trong CODEX_HOME tương ứng; không tự thay tên hoặc đọc lịch sử thật.
- Gates: Ruff, SPA type-check/lint/build và extension type-check/lint/build/package
  pass. VSIX đã cài, host/panel khớp build; Docker rebuild thành công, health/
  readiness 200. Xóa hết pytest/driver/schema/CODEX_HOME và thread thử trong thư mục
  tạm phiên; không thay cấu hình/tên cuộc chat thật. Cảnh báo bundle SPA lớn có từ
  trước. Nút đọc tên chưa được nghiệm thu trực tiếp trong panel sau reload.

## 2026-10-31 ? s?a nh?p XML v? ?? ch?i n?t xem g?i ?

- Scope/files: `xmlBlocks.ts`, `XmlBlockEditor`, `DirectCaptureForm`,
  `useCaptureForm`, `ConnectorError`, `DestinationForm`, `ImprovementTrustCard`,
  locale vi/en v? README extension.
- Implementation: t?i s? d?ng danh s?ch canonical block cho editor v? preflight UI;
  v?n b?n/Markdown ch?n nh?m XML b?o l?i t?i source tr??c khi t?o ?? xu?t. Gi?
  nguy?n n?i dung ?? ng??i d?ng ch?n l?i ??nh d?ng. Preflight c?ng ch?y tr??c
  preview c?a ?? xu?t MCP; backend v?n x?c th?c khi l?u. Kh?ng t? chuy?n format,
  kh?ng g?i provider ho?c ghi revision tr??c x?c nh?n. Preview hi?n th? literal
  XML, m? s?n c? khi unchanged; x?a preview c? khi b?t ??u chu?n b? l?i.
  N?t ?Xem g?i ? tr??c khi ?p d?ng? d?ng shared neutral intent.
- Tests: 21 pytest t?m pass, g?m Unicode/placeholder, text/Markdown ch?n sai XML,
  XML canonical v? verbatim, sai tag/thu?c t?nh/nested/malformed/DOCTYPE/top-level
  text, literal preview, wiring schema/preview v? contrast >=7:1 hai theme.
  Semantic DOM fixture d?ng ElementTree; kh?ng ch?y browser/UI runner. Ki?m tra
  c?c ??u v?o canonical h?p l? b?ng validator backend th?t. ?? x?a file test t?m.
- Acceptance th? c?ng sau reload: d?n Markdown, ch?n XML v? ti?p t?c ph?i b?o r?
  sai ??nh d?ng m? kh?ng m?t n?i dung; ??i Markdown ?? chuy?n ??i sau x?c nh?n.
  XML h?p l? m? preview hi?n ??y ?? th? v? n?i dung. N?t review kh?ng c?n n?n v?ng.
- Gates: Ruff, SPA `pnpm tsc --noEmit`/lint/build v? extension tsc/lint/build/package
  pass. VSIX ?? c?i, hash panel kh?p build. `docker compose up -d --build` exit 0;
  ingress healthz/readyz ??u 200. Ch?a nghi?m thu native UI sau reload. C?nh b?o
  bundle SPA l?n, pytest plugin deprecation v? VS Code CLI DEP0169 t? tooling.
