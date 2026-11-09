# Prope Connector

## Chat PropAI với session Codex

1. Reload VS Code sau khi cài VSIX, mở panel và đăng nhập/chọn workspace.
2. Trong **Kết nối Codex / Claude**, ghép nối rồi bấm **Chọn chat Codex** để chọn tên/ID
   từ danh sách chat của project hiện tại. Hoặc dùng ID đã được MCP ghi nhận.
   Nhãn **Bạn đã chọn** khác **MCP đã ghi nhận**; không tự suy ra tab đang mở.
3. Bấm **Chat PropAI** và xác nhận native. Session được liên kết
   với **Chat PropAI với session agent**; nội dung gốc chỉ giữ trong bộ nhớ extension.
   Chọn chat chỉ đọc metadata, chưa cấp quyền đọc nội dung. Tên được tải tự động;
   metadata/time/phạm vi đọc nằm trong **Chi tiết**. Danh sách dùng `thread/list`,
   lọc project, `useStateDbOnly=true`, 50 mục/trang; không quét JSONL, không gọi model.
4. Panel chỉ hiện tên session, thời gian cập nhật và quyền đọc; không hiện danh sách
   snapshot hay số tin nhắn. Chỉ bấm **Cập nhật nội dung
   session** mới đọc lại history; heartbeat/polling trạng thái không đọc thêm tin nhắn.
5. Gõ câu hỏi và chat trực tiếp với PropAI về session, không cần chọn hoặc đính kèm
   tin nhắn. Extension tìm đoạn liên quan theo câu hỏi trong session đã cấp quyền.
   Ví dụ: “Giải thích prompt xử lý hoàn tiền trong session” hoặc “Lưu prompt vừa
   thảo luận vào Prope”. Agent đề xuất ID tin nhắn nguồn; code chỉ nhận nguyên văn
   tin nhắn đầy đủ đã đọc. Thiếu hoặc mơ hồ thì cần hỏi rõ, không đoán hay ghép đoạn.
6. Duyệt original/canonical trên thẻ. Khi xác nhận lưu, chọn provider/model từ catalogue
   trong hộp chọn VS Code rồi xác nhận binding cuối; không cần nhập credential.
7. Sau lưu, mở revision ngay trong extension để tạo/gắn dataset, chạy eval hoặc cải tiến.
   Chat có thể đề xuất eval và đọc kết quả. Connector không tự thêm released baseline.
   Sau mỗi quyết định, gửi yêu cầu tiếp; không tự chạy queue hoặc model continuation.

Mỗi lượt gửi có thể gọi provider Prope và cần xác nhận chi phí. Nội dung session là
dữ liệu tham chiếu untrusted, không phải system instruction hoặc bằng chứng candidate
tốt hơn; phải dùng eval thật.
**Thu hồi quyền đọc session** ngăn lần đọc/gửi tiếp theo. Đóng panel, đổi user/workspace
hoặc mất kết nối cũng vô hiệu quyền. Không thể rút lại dữ liệu đã gửi provider hoặc
các nội dung đã được backend lưu. Lịch sử được mở trong panel chỉ thuộc grant hiện tại.

Giới hạn hiện tại: Codex local Windows x64; history đọc metadata rồi phân trang
`thread/turns/list(itemsView=full, sortDirection=asc)`. Mỗi phản hồi tối đa 2 MB;
trang quá lớn được đọc lại với ít turn hơn (20 → 10 → 5 → 2 → 1). Toàn lần đọc tối đa
30 giây/32 MB dữ liệu nhận/400 request trang, giữ tối đa 2 MB text và 2.000 turn/tin nhắn.
Một turn riêng vẫn vượt 2 MB thì từ chối, kể cả khi phần lớn là tool output; chọn
chat ngắn hơn hoặc dán prompt vào panel. Session trên 32.768 ký tự vẫn có thể chat:
`sessionContext.ts` truy xuất lexical có chuẩn hóa dấu, dùng thêm câu hỏi trước để
giải tham chiếu; không embeddings hoặc LLM tóm tắt. Mỗi câu hỏi gửi tối đa 32.768 ký tự
JSON/48 đoạn khi cần truy xuất. Session ngắn gửi đủ; session dài có `scope=selected_passages`,
giữ text nguyên văn và đánh dấu đoạn không đầy đủ. PropAI không được nhận là đã đọc hết
session hoặc kết luận nội dung không tồn tại vì không nằm trong trích đoạn. Hỏi cụ thể
hơn nếu chưa đủ evidence; truy xuất từ khóa chưa bảo đảm tìm hết mọi cách diễn đạt.
Import chỉ nhận một tin nhắn `complete=true`, không nhập các đoạn rời thành prompt.
Giới hạn prompt/canonical vẫn giữ nguyên. API có
thể trả item khác vào bộ nhớ host trước lọc; tool/reasoning/file/hook/commentary không
được giữ trong snapshot hoặc gửi backend. Claude history hiện chưa hỗ trợ vì chưa
xác minh liên kết Session ID với MCP; không đoán ID hoặc quét file transcript riêng.

Nếu kết quả ghi/gửi chưa rõ do timeout, các lần ghi tiếp bị chặn. Kiểm tra lịch sử
chat và danh sách prompt/revision trước khi thu hồi, cấp lại quyền để mở phiên mới.
Các request ghi đã hết hạn không chạy sau khi người dùng xác nhận hộp thoại quá muộn.
Chức năng này không thêm dependency, migration DB, quyền approve/release hoặc key/provider
management. Rollback: gỡ VSIX/cài gói trước và hoàn tác đúng phần optional chat-session
API theo `docs/connector-propai-session-plan.md`; không reset các thay đổi khác.

Extension local cho VS Code: dán prompt hoặc mở prompt đã lưu, chỉnh nội dung,
tạo/gắn dataset, đánh giá, cải tiến bằng Prope AI và so sánh revision ngay trong
panel cạnh chat. MCP là cách nhận prompt bổ sung, không bắt buộc để dùng panel.
Không đọc kho chat riêng, không tự thu thập, không approve/release.

## Luồng bằng nút bấm — không cần chat hoặc ghép nối MCP

1. Mở **Prope: Mở panel**, đăng nhập và chọn workspace.
2. Chọn **Dán prompt để bắt đầu**, chọn folder, định dạng và dán nội dung.
   Bấm tiếp tục, đặt tên, chọn provider/model từ catalogue, xem conversion/diff
   rồi xác nhận lưu revision. Hoặc chọn **Mở prompt đã lưu** để tiếp tục.
3. Trong workspace revision, dùng các tab:
   - **Nội dung**: xem nguyên bản, chỉnh canonical XML, chuẩn bị diff để lưu
     revision mới. Backend kiểm tra canonical khi lưu; XML không gọi conversion.
   - **Dataset**: tạo dataset ngay trong drawer và tick để gắn/gỡ. Tạo không
     tự gắn dataset hoặc tự chạy eval.
   - **Đánh giá**: chạy revision trên các dataset đã gắn sau xác nhận chi phí;
     xem lịch sử, từng case và trace. Không cần revision thứ hai; không chạy thêm baseline.
   - **Cải tiến**: chọn eval run đã hoàn tất của revision này, xác nhận gọi Prope
     AI. Đây là provider/backend Prope, không điều khiển model của chat Codex.
     Khi backend có candidate qua gate, bấm xem diff, kiểm tra rồi xác nhận lưu.
     Thiếu evidence hoặc gate từ chối được hiển thị; không tạo candidate giả.
   - **So sánh**: chọn hai revision để xem diff nội dung, chọn canonical hoặc
     nguyên bản, bật/tắt chỉ hiện thay đổi. Không cần dataset hay cùng model;
     không tạo eval run, không gọi provider và không phát sinh chi phí.
4. Candidate và revision mới xuất hiện thành thẻ đề xuất trong cùng panel.
   Đóng panel sẽ bỏ đề xuất chưa lưu; dữ liệu đã ghi có thể mở lại từ danh sách.

Workspace cần có folder và provider đã cấu hình trong Prope. Chỉ các thao tác
dataset/eval/cải tiến trên đây được mở qua transport có schema; không có proxy
HTTP ghi tổng quát. Session đổi/đăng xuất xóa cache và thu hồi đề xuất đang chờ.
Khi kết quả ghi chưa rõ, kiểm tra lịch sử trước khi mở lại prompt và chạy tiếp;
không tự retry tác vụ tốn phí. Lịch sử cải tiến lọc trong 100 agent-run gần nhất
của người dùng. Không dùng draft mock của SPA để tạo revision thật.

## Build và cài đặt (PowerShell)

Cần Node >=22, Corepack và Python >=3.13. Chạy từ thư mục repo:

```powershell
Push-Location src/prope-fe
corepack pnpm install --frozen-lockfile
Pop-Location
Push-Location integrations/vscode
corepack pnpm install --frozen-lockfile
corepack pnpm tsc
corepack pnpm lint
corepack pnpm package
Pop-Location
```

VSIX local được đóng gói bằng ZIP/OPC với Python stdlib, theo manifest mà vsce
sinh ra. Chỉ các file bundle, metadata và bản dịch trong allowlist được đưa vào
gói; không có dependency hay đăng nhập publisher lúc đóng gói.

Trong VS Code, dùng **Extensions: Install from VSIX…** và chọn
`integrations/vscode/dist/prope-connector.vsix`, rồi reload cửa sổ.

Trong Settings đặt `prope.backendUrl` theo cổng Docker đang publish, dùng
`http://127.0.0.1:<port>`. Mặc định là `8080`; repo local có thể override.
Kiểm tra cổng bằng `docker compose port caddy 80`. Reload sau khi đổi setting.
V1 chỉ chấp nhận HTTP loopback `127.0.0.1` hoặc `[::1]` và không đi theo redirect.

## Kết nối Codex / Claude Code (tùy chọn)

1. Chạy **Prope: Mở panel**, sau đó **Prope: Đăng nhập / chọn workspace**.
   Mật khẩu chỉ dùng cho lần đăng nhập; cookie của session riêng được giữ trong
   VS Code SecretStorage, không được gửi vào Webview/MCP.
2. Chạy **Prope: Hiện cấu hình MCP**. Tài liệu mở ra chứa hai phần:
   `claude_mcp_config.mcpServers.prope` để thêm vào cấu hình MCP của Claude Code,
   và chuỗi `codex_config_toml` để thêm vào cấu hình Codex. Không chép nguyên
   tài liệu kết hợp vào một host. Giữ nguyên các server khác.
3. Restart kết nối MCP/session agent theo host. Cấu hình chỉ có `node`, đường dẫn
   adapter và descriptor local; không có session, token hay provider key.
4. Adapter tự đăng ký khi host khởi tạo MCP, không cần model gọi tool hay nhắn chat.
   Chạy **Prope: Ghép nối agent** (hoặc bấm nút trong panel), chọn client đang chờ,
   chọn folder và xác nhận quyền đọc nội dung prompt. Adapter nhận quyền sau tối đa
   khoảng 5 giây. Tên/phiên bản do client tự khai báo, không phải chứng thực danh tính.
   Mỗi adapter cần ghép nối riêng. Yêu cầu chờ hết hạn sau hai phút và tự đăng ký lại;
   nếu hết hạn trong khi đang chọn folder, bấm ghép nối lại. Không tự cấp quyền.
   Nếu danh sách trống, kiểm tra cấu hình và khởi động lại MCP từ giao diện host;
   extension không tự khởi chạy/điều khiển Codex hoặc Claude thay cho host.
   Trong phần **Kết nối Codex / Claude** của panel, xem trực tiếp client đang chờ,
   đã cấp quyền/chờ adapter hoặc đã nhận heartbeat. Bấm **Kiểm tra kết nối** sau
   khi cấp quyền: panel chờ heartbeat mới tối đa 25 giây rồi báo kết quả. Không
   cần gọi `prope_connection_status` trong chat, không tạo prompt hay evaluation.
   Đây là kiểm tra đường adapter–broker/session, không đo chất lượng model hoặc
   chứng minh model đã gọi tool. Đóng phần kết nối sẽ dừng polling danh sách.
   Mỗi kết nối có mục **Cuộc trò chuyện đã dùng kết nối**: adapter lấy `threadId`
   từ `_meta` của lời gọi MCP do host gửi, không lấy từ tool arguments, biến môi
   trường hoặc nội dung chat. Hiển thị ID và thời điểm ghi nhận gần nhất; nhiều
   thread trên cùng kết nối được liệt kê riêng. Không đọc transcript hoặc lịch sử
   chat, không suy đoán tab đang mở. Thiếu metadata thì ghi chưa nhận diện;
   ghép nối/heartbeat không đủ để xác định cuộc chat. Đã kiểm chứng với Codex
   app-server `0.164.0-alpha.11.1` trên máy này, không gọi model; host khác không
   gửi metadata phù hợp sẽ chưa được nhận diện.
   Danh sách nằm trong bộ nhớ, giữ tối đa 32 thread gần nhất mỗi kết nối và mất
   khi kết nối bị thu hồi/hết hạn. Việc nhận diện không thay đổi quyền đọc hiện có:
   quyền vẫn theo kết nối và folder, không phải cấp riêng từng thread. Metadata
   do host gửi không phải cơ chế chứng thực chống giả mạo từ tiến trình local.
   Với client `codex-mcp-client` đã cấp quyền, bấm **Lấy tên từ Codex** trên một
   thread đã ghi nhận để đọc `thread.name` qua Codex app-server `thread/read`
   (`includeTurns=false`). Tên được hiển thị chính, ID là thông tin đối chiếu;
   nút **Cập nhật tên từ Codex** đọc lại khi bạn đổi tên bên host. Không lấy preview
   hay prompt làm tên. API không trả tên thì panel báo rõ; lỗi đọc khác với chưa
   có tên. Chỉ đọc đúng ID đã quan sát trên kết nối được duyệt, kiểm tra lại quyền
   sau khi đọc để không đưa kết quả cũ sang session mới. Tên chỉ ở cache Webview,
   không ghi vào database Prope hoặc log. Không liệt kê toàn bộ lịch sử Codex.
   V1 dùng executable của Codex extension trên Windows x64 (hoặc cấu hình
   `chatgpt.cliExecutable` hiện có), không dùng shell, không tải package mới.
   Chỉ hỗ trợ tên của thread có metadata trong Codex local/CODEX_HOME tương ứng;
   thread remote hoặc host khác có thể chưa đọc được tên. Không gọi model và không
   tự thêm hook, resume, rename hay sửa cuộc chat.
5. Yêu cầu agent gửi đúng một prompt qua `prope_prepare_capture`. Kiểm tra
   nguyên văn, chọn tên/folder đích, provider/model, chuẩn bị conversion rồi
   xác nhận lưu revision trong panel.
   Trường upstream model cần **ID chính xác trong catalogue của provider**, không
   phải tên hiển thị. Nếu nhập nhầm, sửa binding của Draft trong Prope trước khi
   tạo candidate; cả hai revision phải dùng cùng model khi so sánh.
6. Để cải tiến, agent đọc revision được cấp quyền rồi gửi candidate bằng
   `prope_prepare_revision`, gắn đúng `base_version_id`. Panel hiển thị diff.
   Sau khi người dùng xác nhận, gọi lại `prope_connection_status` để nhận ID
   revision hoặc hai run của các đề xuất thuộc kết nối hiện tại.

UI Prope là panel nằm cạnh chat, không phải nút chèn vào tin nhắn riêng của
Codex/Claude. Có thể dùng hướng dẫn tại `skills/prope-chat/SKILL.md` trong repo.

Tài liệu cấu hình chính thức:
[Codex MCP](https://developers.openai.com/codex/mcp),
[Claude Code MCP](https://code.claude.com/docs/en/mcp).

## Evaluation

Mở prompt đã lưu: nếu chỉ có một revision, panel tự chọn bản đó. Trong tab
**Dataset**, tick dataset cần chạy; sang **Đánh giá** để test riêng revision đang
chọn, không cần candidate hay bản release. Connector gửi
`include_released_baseline=false`; API mặc định vẫn giữ hành vi baseline của SPA.

Tab **So sánh** chỉ so sánh nội dung, không đo chất lượng prompt. Đánh giá riêng
revision dùng tab **Đánh giá**. Khi cần đối chiếu chất lượng hai revision trên cùng
dataset, luồng MCP `prope_prepare_evaluation` vẫn có thể gửi đề xuất và yêu cầu
xác nhận chạy; hai revision cần cùng provider/model/parameters. Router combo
chưa được hỗ trợ trong phép so sánh evaluation v1.

Worker đo snapshot canonical đã chốt lúc tạo cặp run, ngay cả khi Draft được
sửa sau đó. Migration `0057` bổ sung snapshot riêng trong eval run và chặn sửa
snapshot. Snapshot không được trả trong response; các API eval cũ giữ cách chọn
baseline và chạy hiện tại.

Mỗi run hiển thị ID, trạng thái, token, chi phí, kết quả assertion và latency
từng case khi có số liệu. Đây là deterministic assertions, không phải LLM judge.
Run chưa hoàn tất/có lỗi không đủ để kết luận candidate tốt hơn. Kết quả không
đánh giá toàn bộ môi trường coding agent.

Hai API management mới (dùng session người dùng và quyền eval hiện có):

- `POST /api/v1/prompts/{prompt_id}/eval-comparisons`: nhận
  `original_version_id`, `candidate_version_id`, `dataset_id` đã gắn; trả hai
  run ID và suite ID với HTTP 202. Connector gửi thêm `original_body_sha256`
  và `candidate_body_sha256` để từ chối nếu nội dung đã đổi trước khi chạy.
- `GET /api/v1/prompts/{prompt_id}/eval-comparisons?original_run_id=...&candidate_run_id=...`:
  đọc đúng cặp run đã tạo, cấu hình đã đo, kết quả từng case và cờ `comparable`.
  Không trả snapshot nội bộ. Các run khác cặp không thể được ghép tùy ý.

Zod được khóa ở 4.6.6 để khắc phục advisory GHSA-mrhx-c7xc-m3w5. Patch đi kèm
chỉ sửa hai comment bị Rollup nhận nhầm là pure annotation; không đổi validator.

## Trạng thái và khôi phục

- Đóng panel xóa đề xuất chưa lưu. Revision/run đã ghi ở backend vẫn tồn tại.
- Workspace/logout thay đổi sẽ thu hồi ghép nối và đề xuất. Adapter mất kết nối
  được thu hồi khi lease heartbeat hết hạn (tối đa khoảng 70 giây).
- Timeout khi ghi có thể xảy ra sau khi backend đã commit. Panel đọc lại lịch
  sử nếu xác định được prompt đích và không tự replay. Kiểm tra registry/eval
  history trước khi gửi đề xuất mới. Nút đóng đề xuất không hủy run đang chạy.
- Mở lại VS Code cần ghép nối lại; descriptor không chứa credential.
- Chỉ một cửa sổ Prope cho mỗi workspace local; v1 chưa hỗ trợ remote windows.
- Search trả tối đa 200 kết quả đã khớp từ backend rồi lọc theo folder được cấp.

## Kiểm chứng và rollback

Chạy backend lint, SPA typecheck/lint/build và extension typecheck/lint/package.
Pytest được tạo/chạy/xóa trong phiên; không chạy UI/e2e test runner.

Nghiệm thu thủ công trong từng host: ghép nối → gửi prompt tiếng Việt → kiểm
tra nguyên văn → từ chối không tạo revision → xác nhận lưu → tạo candidate →
chạy cùng dataset → xem hai run ID. Kiểm tra log VS Code không có prompt/token.

Rollback: gỡ VSIX và chỉ xóa entry MCP `prope` đã thêm; revert code connector.
Có thể giữ cột nullable của migration 0057 khi quay về ứng dụng cũ. Không
downgrade database có evidence cần giữ: downgrade sẽ bỏ snapshot đã lưu.

## Ch?n ??nh d?ng khi d?n prompt

???nh d?ng nguy?n b?n? l? ??nh d?ng ??u v?o. D?n v?n b?n/Markdown th? ch?n
V?n b?n/Markdown; Prope ch? g?i conversion sau khi b?n x?c nh?n chi ph?.
Canonical XML d?ng cho n?i dung ?? c? c?u tr?c Prope, kh?ng ph?i l?a ch?n ??u ra.
Panel ki?m tra XML tr??c khi t?o ?? xu?t tr?c ti?p v? tr??c khi xem preview;
backend ti?p t?c ki?m tra khi l?u. Sai ??nh d?ng gi? nguy?n n?i dung ?? ch?n l?i.
B?n xem tr??c lu?n m? v? hi?n th? nguy?n v?n th? XML, k? c? khi kh?ng c? thay ??i.
