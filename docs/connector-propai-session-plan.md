# PropAI trong extension với nguồn từ session agent

## Yêu cầu đã chốt

- Chat PropAI trong panel VS Code, tái sử dụng UI và backend chat web.
- Chọn cuộc chat từ metadata Codex hoặc ID đã quan sát qua MCP, không suy ra tab đang mở.
- Cấp quyền đọc text người dùng và câu trả lời cuối của duy nhất session đó.
- Chỉ cập nhật snapshot khi bấm nút; không theo dõi lịch sử tự động.
- Session là dữ liệu tham chiếu untrusted, giữ trong extension host. Chat trực tiếp
  không cần chọn tin nhắn; không hiện snapshot hoặc số tin nhắn trong Webview.
- Khi nhập prompt từ session, agent đề xuất ID nguồn; code lấy nguyên văn một tin
  nhắn đầy đủ, còn người dùng duyệt original/canonical trước khi lưu.
- Giữ HITL và permission/RLS; không approve/release hoặc quản trị key/provider qua chat.

## Phase 1 — nguồn và quyền: đã triển khai

Scope/files: `sessionChatContracts.ts`, broker `withCodexConversation`, reader
`codexSession.ts` dùng chung RPC với `codexThreadTitle.ts`, dispatcher extension.

Implementation: native consent theo actor/workspace/connection/thread; kiểm tra scope
trước và sau đọc. Dùng App Server `thread/read(includeTurns=false)` lấy metadata,
rồi `thread/turns/list(itemsView=full, sortDirection=asc)` đọc từng trang của Codex local;
không start/resume turn và không gọi model host. Chỉ giữ `userMessage` text và
`agentMessage` final answer; bỏ ảnh/file, reasoning, commentary, hook và tool items.
API lịch sử có thể trả các item khác vào bộ nhớ extension trước bước lọc; các item
đó không được giữ trong snapshot, hiển thị, gửi backend hoặc log. Không tự đọc file
transcript. ID/tên client là metadata tự khai báo, không phải chứng thực nguồn.

Giới hạn history: toàn lần đọc 30 giây/32 MB dữ liệu nhận, mỗi frame 2 MB; tối đa
400 request trang/2.000 turn/2.000 tin nhắn/2 MB text giữ lại. Trang quá lớn được đọc
lại cùng cursor với ít turn hơn (20 → 10 → 5 → 2 → 1); không tự cắt nội dung. Một turn
riêng vượt 2 MB vẫn bị từ chối và UI hướng dẫn chọn chat ngắn hoặc dán prompt.
Metadata-only giữ giới hạn 15 giây/2 MB. Từ chối history partial, ID trả về khác đích,
cursor/turn/message ID trùng. Snapshot chỉ nằm trong bộ nhớ. Đóng panel,
đổi session/workspace, revoke hoặc hết lease MCP khiến quyền cũ không dùng tiếp được.

Tests: pytest tạm cho protocol, Unicode, lọc item, giới hạn, ID mismatch, revoke race,
workspace/actor isolation. Acceptance native: chưa xác nhận không đọc history; chỉ
đúng thread; bấm cập nhật mới đọc lại. Chưa nghiệm thu native sau cài VSIX mới.

## Phase 2 — chat và workflow prompt: đã triển khai

Scope/files: `sessionChat.ts`, `selectChatBinding.ts`, transport/API và các component
`SessionChat*`, `ChatProvider`, `ChatPromptPreview`; backend
`chat_orchestrator/session_context.py`, schemas, API, router, executors hiện có.

Implementation:

- Transport có schema và thao tác cố định; không thêm HTTP proxy ghi tổng quát hay
  công cụ MCP ghi. Session/cookie/provider key ở host/backend, không vào Webview.
- Tái sử dụng ChatProvider, composer, message, citation và approval card của web.
  SPA giữ transport mặc định; connector dùng JSON qua extension, không tự retry POST.
- Backend nhận `session_context` riêng, không coi cả session là attachment/prompt.
  Router thấy dữ liệu untrusted; responder có evidence/citation trỏ thread/snapshot
  thật do client chia sẻ. Không dùng nội dung chat làm bằng chứng evaluation.
- Ngân sách mỗi câu hỏi giữ 32.768 ký tự JSON; tổng session dài hơn không bị chặn.
  `sessionContext.ts` truy xuất lexical theo câu hỏi và câu hỏi trước, chia đoạn có
  overlap khi tin nhắn quá lớn, giữ nguyên text. Không embeddings hoặc LLM tóm tắt.
  Session ngắn có `scope=full_session`; khi chỉ chọn đoạn có `scope=selected_passages`,
  tối đa 48 đoạn. Không nói đã đọc hết hay suy ra phần không tìm thấy không tồn tại.
  Thiếu evidence thì hỏi cụ thể hơn; không fallback sang trí nhớ mô hình.
- Webview chỉ nhận metadata liên kết, `has_content` và trạng thái quyền; không có
  messages, context_characters hoặc message count. Nội dung chỉ giữ trong host, đọc
  lại khi bấm cập nhật. Trích đoạn thực tế vẫn được backend lưu trong citation của
  lượt chat theo luồng hiện có, không có kho transcript mới.
- Với yêu cầu import_prompt, router có thể đề xuất changes.session_message_id từ
  ngữ cảnh. Backend kiểm tra ID duy nhất, complete=true, part=0, role user/assistant,
  giới hạn prompt; code cấp text gốc cho converter. Host kiểm tra lại preview khớp
  ID/text native trước khi cho xem/duyệt. Đoạn thiếu, ID sai, nguồn mơ hồ không được
  nhập. Attachment truyền thủ công từ client cũ vẫn giữ kiểm tra cũ.
- Không tự lấy attachment cũ để nhập prompt mới. Revision cải tiến từ prompt đã lưu
  dùng drafter hiện có và base được backend đọc theo ACL.
- Thẻ duyệt prompt hiển thị original/canonical XML nguyên văn trước lưu. Khi xác nhận,
  native picker chọn provider/model từ catalogue thật và hộp xác nhận cuối hiển thị
  binding cụ thể. Binding được ghi vào proposal và revision trong transaction sẵn có.
  Với revision có base, kiểm tra lại version/body và giữ parameters/fallback của base.
- Chat connector chỉ xác nhận create_prompt/create_revision/start_eval_run. Evaluation
  connector chạy revision được chọn, không tự thêm released baseline; web giữ mặc định cũ.
- Sau quyết định không tự chạy queue/model continuation: người dùng gửi yêu cầu tiếp
  với snapshot/quyền còn hiệu lực. Kết quả đã lưu mở được RevisionWorkspace trong panel.
- Mỗi send/approve tốn phí hoặc ghi có native HITL; request hết hạn sau 175 giây.
  Sau timeout/outcome chưa rõ, host và Webview chặn ghi/gửi lại; chỉ cho đọc lịch sử.
  Refresh snapshot không xóa trạng thái chưa rõ. Kiểm tra dữ liệu trước khi cấp lại quyền.
- Lịch sử trong extension chỉ thuộc cuộc PropAI chat của grant hiện tại. Đóng panel
  xóa liên kết trong bộ nhớ; không xóa hội thoại đã lưu ở backend.
- Log gồm request ID, operation, status và latency; không có transcript, title hoặc key.

Tests: pytest tạm kiểm tra profile tool, context/citation thật từ fixture, preview
đúng arguments, xác nhận/thu hồi/timeout, provider binding qua executor thật với DB
mock, base đổi, baseline mặc định web và standalone connector. Không gọi provider.

Acceptance: chọn source → xác nhận đọc → chat → duyệt prompt → chọn
  binding → lưu → mở revision/dataset/evaluation trong extension. Chưa nghiệm thu native.

## Phase 3 — host và đóng gói

- Codex local Windows x64: đã đối chiếu schema CLI đang cài và tài liệu App Server.
- Claude: SDK có `getSessionMessages`, nhưng implementation hiện tại chưa xác minh
  được Session ID thật gắn với kết nối MCP. Nút đọc history bị vô hiệu hóa; không đoán
  ID, đọc file riêng hoặc hứa đã kết nối. MCP capture Claude hiện có vẫn giữ nguyên.
- Không thêm dependency, env var hoặc migration DB cho chức năng này.
- Gates: Ruff, SPA/extension type-check/lint/build/package; cài VSIX, rebuild Docker
  và health/readiness. Kết quả cuối được cập nhật sau khi hoàn tất.
- Tests/driver/schema tạm phải xóa trước khi kết thúc; không UI/e2e runner.

## Dữ liệu và rollback

Tin nhắn có thể chứa dữ liệu nhạy cảm: native consent trước đọc và trước gửi trích đoạn.
Thu hồi ngăn truy cập tiếp theo và bỏ tham chiếu cache local; không rút lại nội dung
đã gửi provider, câu trả lời/trích nguồn hoặc prompt đã được backend lưu.

Rollback bằng gỡ VSIX hoặc cài lại gói trước nếu có. Khi rollback code, chỉ hoàn tác
phần chat-session trong các file nêu trên và optional API context/binding; không reset
toàn working tree vì có thay đổi connector khác từ các phiên trước. Không cần rollback
migration DB cho tính năng này.

## Nguồn xác minh

- https://learn.chatgpt.com/docs/app-server#read-a-stored-thread-without-resuming
- https://code.claude.com/docs/en/agent-sdk/sessions

## Kết quả kiểm chứng

- 55 ca pytest logic/protocol pass và 1 ca bổ sung xác nhận source giữ nguyên cả
  khoảng trắng/xuống dòng. Fixtures dùng broker loopback thật, RPC/native picker
  mô phỏng và backend executor thật với DB mock; không dùng chat/private data thật,
  không gọi provider hoặc chạy evaluation tốn phí.
- Ruff, SPA `pnpm tsc --noEmit`/lint/build và extension tsc/lint/build/package pass.
- VSIX đã cài; host/panel đã đối chiếu hash với build. Docker rebuild thành công,
  healthz và readyz trên ingress đều trả 200.
- Đã xóa toàn bộ 334 file test/driver/bundle/schema tạm do phiên tạo và hai thư mục
  fixture. Không thêm test dependency/config vào repository; không chạy UI/e2e.
- Cảnh báo còn có từ tooling: bundle SPA lớn, pytest plugin deprecation và VS Code
  CLI DEP0169. Không suy ra đã nghiệm thu native hoặc đã có evaluation evidence.
- Nghiệm thu native còn cần người dùng reload VS Code, ghép nối lại nếu cần, cấp
  quyền đúng thread, kiểm tra snapshot và tự xác nhận gửi/lưu/eval theo workflow.

## Bổ sung: chọn chat không cần gọi tool trong chat

Heartbeat không có Thread ID; sau restart/re-pair, chưa có tool call thì danh sách
MCP có thể trống. Thêm `choose_conversation` trên Webview, chỉ nhận connection ID.
Broker kiểm tra pair đã cấp quyền/Codex/actor/workspace trước và sau native picker.
Picker đọc `thread/list` metadata, lọc cwd project, `useStateDbOnly=true`, tối đa
50 mục/trang và 10 trang do người dùng bấm; không dùng preview làm tên, không đọc
history, không gọi model. Tên/ID chọn phải đến từ danh sách API; client không truyền ID.

Record được đánh dấu `user_selected_codex_thread`, không giả làm MCP observation.
Khi MCP thật báo cùng ID thì nâng thành `mcp_metadata_thread_id`, không hạ ngược.
Vẫn giới hạn 32 record; chọn metadata không cấp quyền đọc history hoặc đổi folder grant.
Muốn đọc snapshot vẫn phải xác nhận native qua Chat PropAI như trước.

UI kết nối gọn: tên client/mã/trạng thái/folder một hàng, hai nút chọn/kiểm tra;
tên chat tự tải qua hàng đợi giới hạn, ID luôn hiện, giải thích dài thu gọn trong Chi tiết.
17 ca pytest protocol/scope/picker/queue pass; dùng fixture, không UI/e2e runner.
Đã gọi `prope_connection_status` thật trước sửa: connected=true, finance, không đề xuất.
Kiểm tra `thread/list` thật trong project trả 10 chat, cả 10 có name; chỉ in số lượng,
không đọc history hoặc chọn/gán chat thay người dùng. Cwd filter xử lý cả chữ hoa/thường
của ký tự ổ đĩa Windows; vẫn chỉ lọc cùng project. Không có fallback quét transcript.

## Kiểm chứng luồng hỏi theo session, không hiện snapshot

- 31 pytest tạm và 2 ca bổ sung pass: truy xuất session dài, câu hỏi tiếp nối, Unicode/chunk và ngân
  sách JSON; state/grant không trả message hay số lượng cho Webview; scope/consent,
  refresh lỗi, unknown outcome và nguồn giả; orchestrator thật với model/DB fixture
  chỉ tạo proposal từ nguồn đầy đủ, giữ nguyên luồng web và kiểm tra trùng prompt.
  Hai ca bổ sung xác nhận chỉ dùng câu hỏi trước khi còn cùng cuộc chat PropAI;
  bắt đầu chat mới không mang theo từ khóa của cuộc PropAI chat trước.
- Ruff và SPA/extension type-check/lint/build/package pass. Không thêm dependency,
  env var hoặc migration. Không chạy model thật hay UI/e2e test runner.
- Audit production của extension: 0 advisory. Frontend: 8 advisory có sẵn trên
  fast-uri 4.1.3 qua peer Ajv tùy chọn (2 high, 4 moderate, 2 low). Import trong app
  chỉ dùng @hookform/resolvers/zod; entry Zod/root resolver không import Ajv và không
  có dấu vết fast-uri/Ajv trong bundle đã kiểm tra. Không nâng dependency ngoài scope.
- Truy xuất hiện tại là từ khóa có chuẩn hóa dấu; câu hỏi chung về toàn bộ session
  dài có thể chưa đủ evidence. Chỉ tin nhắn đầy đủ, nằm trong ngân sách mới được
  nhập nguyên văn; trích đoạn không được ghép lại hoặc nhận là prompt đầy đủ.
- Nghiệm thu native vẫn cần reload, chọn session/cấp quyền, đặt câu hỏi cụ thể và tự
  xác nhận bước gửi/lưu/eval. Các ca kiểm thử dùng fixture, không khẳng định model
  thật đã chọn đúng nguồn hay câu trả lời tốt hơn.
