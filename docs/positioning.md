# Positioning & USP — Prope

> | | |
> |---|---|
> | Trạng thái | **v3 — 2026-08-06** — đã hợp nhất với nguồn chân lý sản phẩm và phân tích nghiệp vụ |
> | Tên sản phẩm | **Prope** *(đã chốt — thay cho `{{PRODUCT}}` của v2 và `Promptrope` cũ)* |
> | Brand idea | **Prompt as property** — *Prompt là tài sản* |
> | Slogan | **Your prompt. Your property.** |
> | Nguồn chuẩn | [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) — thắng mọi tài liệu khác khi mâu thuẫn |
> | Nguồn nghiệp vụ | [`docs/business-analysis.md`](business-analysis.md) |
> | Nguồn nghiên cứu | [`docs/RESEARCH.vi.md`](RESEARCH.vi.md) · [`docs/RESEARCH.md`](RESEARCH.md) — 116 nguồn, 68 được trích dẫn. Số `[n]` trỏ tới mục Sources của báo cáo đó. |

---

## 0. v3 đã đổi gì so với v2 (đọc phần này trước)

| # | Thay đổi | Vì sao |
|---|---|---|
| 1 | **Chốt tên: Prope.** Find-replace toàn bộ `{{PRODUCT}}` và `Sổ`. | Nguồn chân lý §18 quy tắc 1: dùng **Prope**, không dùng Promptrope. |
| 2 | **Gắn định vị vào brand idea "prompt là tài sản".** Category cũ ("sổ tài sản prompt") vốn đã trùng khớp — giờ nó có brand đứng sau, không còn là ẩn dụ tự phát. | Nguồn chân lý §1, §9. |
| 3 | **Đảo thứ tự trụ cột: ① hỗn loạn → ② HITL → ③ chi phí.** | Chính v2 đã viết HITL là "thứ mạnh nhất trong toàn bộ định vị" nhưng lại xếp thứ ba. Priority matrix cũng xếp S6 (review) ở P1 còn S9 (cost) ở P2. |
| 4 | **Nói thật về nền bằng chứng của trụ cột chi phí: yếu nhất trong ba.** Chỉ **2/11** người khảo sát doanh nghiệp từng gặp chi phí tăng bất ngờ. | Nguồn chân lý §5.1 và §15 (S9: impact 2, "defer and validate"). Bán một trụ cột bằng nỗi đau mà 9/11 người không có là cách nhanh nhất để mất uy tín ở vòng hỏi vặn. |
| 5 | **Thêm số liệu khảo sát thật vào phần vấn đề** (enterprise n=11, individual n=15) thay cho lập luận thuần suy diễn. | Nguồn chân lý §5. Kèm cảnh báo: đây là bằng chứng **định hướng**, không đại diện thống kê (§21). |
| 6 | **Thêm chế độ cá nhân (individual mode)** — v2 hoàn toàn là câu chuyện doanh nghiệp. | Nguồn chân lý §4.4, §7 Insight 7, H-07: cá nhân cần *lưu → tìm → dùng lại*, không cần bộ máy quản trị. |
| 7 | **Chuẩn hoá thuật ngữ theo language system.** `version` → **revision**; `rollback` → **restore**; `promote` → **release**; `share` → **grant access**; trạng thái giữ nguyên literal: Draft / In review / Approved / In use / Retired. | Nguồn chân lý §8, §18. |
| 8 | **Thêm §12 — bảng căng thẳng giữa định vị và nguồn chân lý.** Ba chỗ hai tài liệu chưa khớp: phạm vi scanner, cổng chi phí, và "hot path". | Phân tích nghiệp vụ §11 xếp cả ba vào nhóm cần chốt trước khi code. |
| 9 | **Thêm ranh giới pháp lý của chính chữ "tài sản".** | BR-09: "property" là ẩn dụ sản phẩm, **không** xác lập quyền sở hữu trí tuệ. Với một brand tên là *Prope*, đây là rủi ro thông điệp lớn nhất, không phải chú thích nhỏ. |

---

## 1. Positioning statement (bản chính)

> **Cho** các đội sản phẩm trong tập đoàn — nơi prompt của sản phẩm AI đang nằm rải rác trong code, Google Sheet, Notion và chat cá nhân,
> **Prope là** sổ tài sản prompt (prompt asset register) dùng chung cho toàn tập đoàn,
> **giúp** biến prompt từ một đoạn text cá nhân thành tài sản có chủ sở hữu, có lịch sử revision, có quyền truy cập rõ ràng và có bằng chứng chất lượng — trước khi nó được release lên production,
> **khác với** các nền tảng LLMOps hiện có (Langfuse, LangSmith, Braintrust, Bedrock/Vertex Prompt Management) vốn được thiết kế cho developer và chỉ biết đến những prompt đã nằm sẵn trong hệ thống,
> **Prope bắt đầu từ chính sự hỗn loạn có thật** — gom prompt đang rải rác khắp nơi — và cho người **không phải developer** (marketer, designer, PM) dùng được ngay từ ngày đầu.

### Slogan (brand, đã chốt)

> **Your prompt. Your property.**
> *Prompt của bạn. Tài sản của bạn.*

### One-liner (category)

**Sổ tài sản prompt của tập đoàn — không phải thêm một dashboard AI ops.**
*(EN: The company's prompt asset register — not another AI ops dashboard.)*

### Positioning line (nguồn chân lý §9)

> Biến những prompt mà đội của bạn đang phụ thuộc thành tài sản có chủ sở hữu, được bảo vệ và sẵn sàng cho production.

### Elevator (30 giây)

> Mọi công ty làm sản phẩm AI đều có một tài sản vô hình đang bị thất thoát: prompt. Chúng nằm rải rác trong code, Sheet, Notion, chat riêng của từng người — **10/11 người chúng tôi khảo sát lưu prompt trong lịch sử chat, và không ai dùng một công cụ chuyên dụng nào.** Không ai biết bản nào đang chạy production, không ai restore được, và khi một người nghỉ việc thì prompt tốt nhất của họ biến mất theo.
> Prope gom số prompt đó về một registry, gắn cho mỗi prompt một chủ sở hữu, một lịch sử revision và một trạng thái rõ ràng — rồi bắt mọi thay đổi phải đi qua một quyết định duyệt có ghi nhận trước khi được release lên production.

### Bài kiểm tra ngày-90 (định nghĩa "tài sản" theo cách có thể bị bác bỏ)

> Lấy ngẫu nhiên 20 prompt vào ngày thứ 90. Kiểm tra 4 trường:
> **chủ sở hữu · trusted revision + trạng thái vòng đời (có đường Retired) · đang được sản phẩm nào dùng (Used by) · chi phí.**
> Nếu bất kỳ trường nào trống, cũ, hoặc phải có người *nhớ* để cập nhật — thì đây là một database có cái tên đắt tiền, và marketer quay lại Google Sheet là đúng.

> ⚠️ **Trường thứ tư có điều kiện.** Chi phí phụ thuộc telemetry, mà telemetry nằm ở S9 — **P2, "defer and validate"** trong priority matrix. Ở bản MVP, bài kiểm tra ngày-90 chạy với **ba trường đầu**. Đừng hứa trường thứ tư trong pilot đầu tiên rồi trượt nó.

**Luật thiết kế rút ra:** *mọi trường vận hành phải được sinh ra từ một hành động ai đó vốn dĩ đã làm.*
Chủ sở hữu ← ai bấm Approve. Trusted revision ← chính hành động Approve. Used by ← API/SDK gọi. Chi phí ← telemetry.
Trường duy nhất không tự sinh được — *prompt này để làm gì* — được thu thập **bên trong** đúng bước review mà ta vốn đã bắt buộc.

---

## 2. Category

Chúng ta **tự định nghĩa category**, không nhảy vào category có sẵn:

| | |
|---|---|
| ❌ Không phải | LLM observability / tracing platform |
| ❌ Không phải | Prompt playground / prompt marketplace |
| ❌ Không phải | Eval framework |
| ❌ Không phải | Thư viện prompt / kho template |
| ❌ Không phải | Sổ đăng ký quyền sở hữu trí tuệ |
| ✅ Là | **Prompt Asset Register** — registry tài sản prompt + lớp quản trị release cho tổ chức |

**Vì sao tự định nghĩa category:** nếu vào category "LLMOps observability", ta phải đấu tay đôi với Langfuse (open-source, miễn phí, 30K sao) và thua ngay ở bảng feature. Category "tài sản của tổ chức" là category ta viết luật chơi: đơn vị đo không phải trace/span, mà là *chủ sở hữu, revision, trạng thái, quyền truy cập, chi phí*.

> **Lưu ý ngôn ngữ.** Trong tài liệu chiến lược (chính tài liệu này) dùng thoải mái "tài sản", "asset register", "governance". Trong **copy hiển thị cho người dùng** thì tiết chế: nguồn chân lý §7.3 quy tắc 8 yêu cầu tránh lạm dụng "asset", "governance", "lifecycle". Trên UI: **Registry**, **Portfolio**, **Prompt Owner**, **Revision**, **Trusted revision**, **Grant access**, **Restore**.

---

## 3. Đối tượng & frame of reference

### 3.1 Ba vai chuẩn (nguồn chân lý §4) và persona nghiên cứu tương ứng

| # | Vai chuẩn | Persona nghiên cứu | Cần gì | Cảm giác mong muốn |
|---|---|---|---|---|
| 1 | **Prompt Owner** | Minh + Toàn (Designer & Marketer) | Đưa prompt vào không cần code, xác lập quyền sở hữu, tìm lại, giữ revision, kiểm soát ai truy cập | "Công việc của tôi được giữ lại, được ghi nhận, và an toàn để dùng lại." |
| 2 | **Reviewer / Approver** | Toàn (Manager) | Thấy owner, thấy cái gì đã đổi, so sánh chất lượng/chi phí/rủi ro, để lại quyết định có ghi nhận | "Tôi bảo vệ được chất lượng mà không trở thành nút thắt." |
| 3 | **Developer / AI Engineer** | Quân (Dev) | Chỉ lấy revision đã Approved, pin version ID, biết cái gì đang chạy, release và restore an toàn | "Prompt đang chạy production là bản đã biết, đã duyệt, và khôi phục được." |

**Thứ tự ưu tiên là có chủ đích: Prompt Owner đứng số 1.** Mọi đối thủ đều xếp họ ở hạng cuối. Dev là **số 2, không phải số 1** — nhưng có **quyền phủ quyết**.

> **Lưu ý từ research:** dev là người ít ảnh hưởng nhất tới việc marketer có dùng hay không — **cho tới lúc** register gây sự cố production, lúc đó team dev cấm dùng và công cụ của marketer chết theo. Xem §12 về việc điều này ràng buộc kiến trúc ra sao.

### 3.2 Chế độ cá nhân — một câu chuyện khác, không phải phiên bản rút gọn

Nguồn chân lý §4.4 và Insight 7 nói rõ: **không được phơi toàn bộ mô hình quản trị ra làm trải nghiệm cá nhân mặc định.**

| | Doanh nghiệp | Cá nhân |
|---|---|---|
| Vòng lặp cốt lõi | Register → Own → Review → Approve → Release → Restore | **Lưu → Tìm → Dùng lại → Giữ lịch sử** |
| Ngôn ngữ | Ownership · provenance · trusted revision · access · review · release | Prompt của bạn · công việc của bạn · giữ lại · tìm lại · dùng lại |
| Cảm giác | Bảo vệ tổ chức khỏi rủi ro | Bảo vệ tay nghề cá nhân |

Bằng chứng cá nhân (n=15) ủng hộ đúng vòng lặp hẹp này: 13/15 tạo nhiều prompt gần giống nhau, 13/15 sửa mà không giữ bản cũ, 12/15 không nhớ bản nào chạy tốt nhất. Cái họ muốn nhất: **một nơi duy nhất để giữ (8/15)** và **tìm nhanh (7/15)** — không phải approval workflow.

### 3.3 Ta đang thay thế cái gì (frame of reference thật)

Không phải Langfuse. Là **Google Sheet + Notion + Drive + tài khoản dùng chung + một đoạn chat có sẵn prompt**.

Đây không phải phỏng đoán: **10/11** người khảo sát lưu prompt trong lịch sử chat, trung bình **~3 nơi lưu mỗi người**, **0/11** dùng bất kỳ prompt manager chuyên dụng nào, và **0/11** dùng thư viện prompt dùng chung.

> **Tiêu chí thắng thua:** không phải "ngang tính năng với Langfuse", mà là **"được dùng nhiều hơn Google Sheet trong chính tập đoàn này"**.
> Mọi tính năng phải được chấm điểm theo thước đo đó.

---

## 4. USP — 3 trụ cột

Ba trụ cột không phải ba tính năng. Chúng là **ba thời điểm mà cuốn sổ tự ghi chính nó**: ingestion ghi danh tính và nguồn gốc, cú bấm Approve ghi chủ sở hữu và trạng thái vòng đời, telemetry ghi lượt dùng và chi phí.

Thứ tự dưới đây phản ánh **cả độ mạnh của lập luận lẫn priority matrix của nguồn chân lý** (§15).

---

### USP #1 — Bắt đầu từ hỗn loạn, không bắt đầu từ trang trắng
**"Có giá trị trong 10 phút đầu, trước khi bạn di chuyển bất cứ thứ gì."**

Gom prompt từ repo, Google Sheet, Notion, Drive, chat export → trích xuất → gom cụm bản gần trùng → trả về bản đồ hiện trạng.

**Hiển thị theo kiểu hai quần thể, không phải một con số:**

> ❌ "Tập đoàn có 213 prompt."
> ✅ **"412 đã phát hiện, 38 đã được quản trị."**

Prompt nhập hàng loạt rơi vào trạng thái **chưa được nhận (ungoverned)**, bị loại khỏi mọi thống kê quản trị, và các trường ngữ nghĩa để trống chứ **không** để AI đoán. Lý do: nhập hàng loạt tạo ra đúng cái mục rữa mà register sinh ra để ngăn — một cuốn sổ to, đẹp, và rỗng nghĩa vào ngày thứ 30. Một cuốn sổ **phân biệt được cái nó biết với cái nó chỉ đang giữ** là cuốn sổ duy nhất đáng tin.

**Ràng buộc bắt buộc (BR-01):** import **private mặc định**, **không auto-publish, không auto-share, không auto-release**. Đây không phải tuỳ chọn — 1 trong 4 rào cản adoption hàng đầu trong khảo sát là "ngại chia sẻ prompt cá nhân".

**Vì sao đối thủ không có:** toàn bộ Tier 1–4 chỉ biết đến prompt **đã nằm trong hệ thống của họ**.

**Nói thật về mức độ chắc chắn:** không nguồn nào cho thấy đối thủ làm được việc này — đó là bằng chứng về **tính mới**, không phải bằng chứng về **tính hiệu quả**. Chưa ai đo được rằng ingestion tự động thực sự tạo ra adoption.

**Giới hạn kỹ thuật cần nói trước:** hai phương pháp discovery của ngành bảo mật đều mù ở đúng chỗ ta cần — quét code không thấy Sheet/Notion/chat, bắt traffic ở egress không quy được về prompt nào. **Connector cho tài liệu là phương pháp thứ ba và bắt buộc**, và register phải ghi lại *prompt này được tìm ra bằng cách nào*.

> ⚠️ **Khoảng cách phạm vi cần biết.** Nguồn chân lý §16 định nghĩa MVP là **"add và import prompt"** (S4 — copy-paste, save selected text, import Sheets/Notion/repo/file, preview trước khi đăng ký). **Quét tự động toàn tập đoàn không nằm trong MVP.** Xem §12 mục T1.

---

### USP #2 — HITL mà người duyệt quyết được trong 2 phút
**"Một màn hình. Duyệt hoặc không."**

**Đây là trụ cột mạnh nhất trong toàn bộ định vị:**

> **"Đối tượng quyết định duyệt" (approval-decision object) — không nhà cung cấp nào bán thứ này.**

Ở Langfuse, PromptLayer, Bedrock, Vertex, "promote" chỉ là **một lượt ghi có phân quyền vào một cái nhãn**. Không có trạng thái chờ duyệt, không có hồ sơ bằng chứng, không tách người đề xuất khỏi người quyết, không có đường từ chối. Chính Langfuse ghi trong bảng năng lực của họ rằng multi-step approval workflow là **Composed**, không phải **Native**.

Bốn lập luận độc lập cùng trỏ về một component:
1. Đây là **khoảng trống thị trường** đã được chính nhà cung cấp thừa nhận.
2. Đây là **bề mặt tự xây được phép** theo bài test build-vs-buy trung thực.
3. Đây là **đầu ra của agent** — thứ con người nên review là một thẻ bằng chứng, không phải một diff thô.
4. **Đây là chỗ trống lớn nhất trong khảo sát:** **0/11** đội có quy trình phê duyệt chính thức; 6/11 để người tạo prompt tự quyết. Không có gì để thay thế — chỉ có chỗ trống để lấp.

Và nó là **trigger ghi** cho chủ sở hữu, trusted revision, trạng thái vòng đời và cả hai trường ngữ nghĩa — trong **một hành động duy nhất**.

**Thẻ quyết định gồm:** diff bằng ngôn ngữ hệ quả · delta chất lượng · delta chi phí · blast radius (Used by — sản phẩm nào đang dùng) · khuyến nghị.

Kèm cờ `ai-drafted` / `human-confirmed` để **tự đo tỷ lệ duyệt lấy lệ của chính mình**.

Bắt buộc có **đường thoát hiểm (break-glass)**: owner được phép release khẩn, có log lý do một dòng, sinh task review trong 24h — nếu không, người ta sẽ đi vòng qua cổng vĩnh viễn.

**Kỷ luật chống bureaucracy (Insight 4 + rào cản adoption #4 "sợ approval làm chậm việc"):** **một cấp review, một reviewer**. Không multi-level approval trong MVP. Mục tiêu đã ghi: median review **dưới một ngày làm việc**, và ≥70% người dùng báo **không** bị chậm đáng kể.

---

### USP #3 — Chi phí là cổng chặn, không phải biểu đồ
**"Bản này tốt hơn 3% nhưng đắt hơn 40% — bạn vẫn muốn release chứ?"**

**Sửa quan trọng — đo cái gì:** **KHÔNG đo token của prompt.** Có trường hợp ghi nhận cắt ~17% input token mà **tổng chi phí phiên tăng ~67%**, vì model phải "trả tiền" để suy luận lại phần ngữ cảnh đã bị cắt (thêm reasoning, thêm retry, thêm vòng sửa).

> Đo **chi phí trên mỗi tác vụ hoàn thành thành công**, tính cả retry và các lượt hội thoại phục hồi, quy về từng revision.

Một cổng cảnh báo theo độ dài prompt sẽ **im lặng khi chi phí tăng** và **kêu khi chi phí giảm** — tệ hơn là không có cổng, vì nó sai một cách tự tin.

**Trình tự triển khai:** **showback trước, chargeback sau.** Cho mỗi team thấy con số của họ trước khi gắn tiền thật vào, để lộ ra các lỗ hổng gắn thẻ. Chỉ chuyển sang chargeback khi độ phủ thẻ và độ chính xác đếm token đủ để qua audit.

> ⚠️ **Đây là trụ cột có nền bằng chứng yếu nhất — nói thật điều đó.**
> Chỉ **2/11** người khảo sát doanh nghiệp từng gặp chi phí tăng bất ngờ, so với **11/11** không tìm được prompt cần và **11/11** không biết revision mới nhất. Priority matrix xếp S9 ở **P2, impact 2, "defer and validate"**.
> **Cách dùng đúng:** giữ nguyên lập luận "đo sai còn tệ hơn không đo" — nó đúng và nó hiếm — nhưng **đừng dẫn pitch bằng chi phí**, và đừng để nó chiếm thời lượng ngang hai trụ cột trên. Xem §12 mục T2.

---

### USP hỗ trợ #1 — Eval: chặn / trình bày / theo dõi (KHÔNG "đảm bảo")

Ràng buộc gốc viết "eval hồi quy để đảm bảo không giảm chất lượng". **Không thể thực hiện lời hứa đó dưới dạng một phán quyết tự động.** Thay bằng ba phần bắt buộc:

| | Làm gì | Vì sao |
|---|---|---|
| **CHẶN** | Tự động, và chỉ trên các thuộc tính hợp đồng kiểm được bằng code: đúng schema, có disclaimer bắt buộc, không có cụm từ cấm, độ dài, độ trễ, chi phí, không lộ credential | Đây là bài toán *hợp đồng*, không phải bài toán *chất lượng*. Chỉ loại này mới chạy được ở độ tin cậy mà chữ "cổng chặn" ngụ ý |
| **TRÌNH BÀY** | Chất lượng chủ quan hiện ra như **bằng chứng để phân xử**, không bao giờ là điểm số | Judge gần như không mang thông tin xếp hạng trên nội dung sáng tạo (ρ≈0, khoảng tin cậy chứa 0) — đúng loại việc mà marketer/designer của ta làm |
| **THEO DÕI** | Chạy lại đúng bộ hợp đồng đó theo lịch, đối chiếu với model đang phục vụ | Cổng trước release **về mặt cấu trúc** không thấy được drift: GPT-4 từng rơi 84%→51% ở một tác vụ mà **không có thay đổi version nào** |

**Cách trình bày chất lượng chủ quan — ý tưởng tốt nhất trong toàn bộ nghiên cứu:**

> Đừng đưa điểm số. Dùng judge để **CHỌN 3–5 input production mà output cũ và mới lệch nhau nhiều nhất**, rồi đặt cạnh nhau cho người duyệt tự phân xử.
> Chọn ví dụ là bài toán **truy hồi (retrieval)**, không phải **xếp hạng (ranking)** — nên nó **không dính** vào chỗ mà độ tin cậy của judge sụp đổ.

**Ranh giới phân quyền vẽ sai chỗ nếu chỉ vẽ quanh "ai được sửa text" (BR-10).** Nút thắt chất lượng thật nằm ở vòng eval, không ở câu chữ. Vì vậy: **sửa nội dung prompt → mở cho non-dev**; **sửa ngưỡng và danh mục hợp đồng eval → vai trò hẹp hơn, có review**.

**Không được tuyên bố "đảm bảo không giảm chất lượng" ở bất kỳ bề mặt nào** (NFR-04). UI phải nêu rõ loại bằng chứng và giới hạn của nó.

### USP hỗ trợ #2 — Là một lớp, không phải một sự thay thế

Đồng bộ revision đã Approved **xuống** runtime mà từng team đang dùng (Bedrock, Vertex, self-hosted), kéo telemetry **ngược về** qua OpenTelemetry.

**Bề mặt tự xây tối thiểu — 4 + 1:** (1) schema tài sản xuyên nhà cung cấp, (2) đối tượng quyết định duyệt, (3) adapter đẩy xuống từng runtime, (4) thu telemetry **không chứa nội dung** (chỉ `gen_ai.usage.*`), **cộng** (5) gom cụm trùng lặp như một **cơ chế bù thường trực** — vì versioning theo nhãn **không có branch/merge**, hai người sửa lệch nhau sẽ đẻ ra một "tài sản" gần trùng mới, và chỉ clustering bắt được. *(Trong nguồn chân lý, (5) là S8 — P2, "defer and validate", và chỉ được là **cảnh báo/triage**, không bao giờ tự merge hay tự đổi owner — FR-10.)*

Telemetry không chứa nội dung có nghĩa là: **điền được trường chi phí cho sản phẩm khách hàng của công ty con mà không cần đọc dữ liệu người dùng của họ.** Biến một rào cản data-governance thành một giá trị mặc định.

---

## 5. Reason to believe

| Tuyên bố | Bằng chứng cần có ở demo |
|---|---|
| Biến prompt thành tài sản | Mỗi prompt có Owner, Trusted revision, trạng thái, Used by (số sản phẩm đang dùng), lần dùng cuối — và chi phí/tháng *khi telemetry đã có* |
| Bắt đầu từ hỗn loạn | Demo import một repo + một Sheet thật, ra bản đồ hiện trạng trong < 2 phút, hiển thị **"N đã phát hiện, M đã quản trị"** |
| Duyệt trong 2 phút là thật | Một màn hình: diff hệ quả + 3 ví dụ output lệch nhau đặt cạnh nhau + delta chi phí + blast radius |
| Không còn Blind Box | Từ 1 output lỗi ngoài production → truy ngược ra revision + model + biến đã sinh ra nó |
| Người không biết code dùng được | Cho một người không phải dev tạo & submit một revision trong demo, không dòng code nào |
| Restore nhanh | Đưa environment về một revision đã Approved trước đó, có audit event, **dưới 5 phút** |
| Chi phí có người chịu trách nhiệm | Cảnh báo delta chi phí **trên mỗi tác vụ thành công** chặn được một release ngay trên sân khấu *(phụ thuộc telemetry — xem §12 T2)* |

### Ba công cụ tự chứng minh sai (ship kèm sản phẩm)

Định vị này có thể sai, và ta nên là người phát hiện ra điều đó trước:

1. **Nếu lần import đầu tiên vào Drive/Sheet của tập đoàn cho tỷ lệ trùng lặp thấp hơn nhiều so với 30.4%** (tỷ lệ trùng lặp ngữ nghĩa nội bộ đo được trên một quần thể git *có tổ chức tốt hơn nhiều*) → tiền đề gốc yếu, phải rescope sản phẩm quanh revision control thay vì discovery.
2. **Nếu tỷ lệ sửa trường "mục đích" gần bằng 0 trong pilot** → tầng ngữ nghĩa không đáng tin, và phải mô tả nó đúng như vậy (tức là bước review đang bị làm cho có).
3. **Nếu người dùng export bảng ra Google Sheet trong tuần đầu** → view trong Registry chưa trả lời được câu hỏi thật của họ. Đây là dấu hiệu cảnh báo kinh điển của mọi hệ thống bị bỏ rơi.

Cả ba phải được **instrument sẵn**, không phải khảo sát thủ công.

---

## 6. Anti-positioning — những gì Prope KHÔNG làm

- **Không làm tracing/observability.** Langfuse miễn phí và làm tốt hơn. Ta tích hợp, không cạnh tranh.
- **Không chỉ là một thư viện prompt hay kho template.** Nếu bỏ ownership, revision và trusted path to production, cái còn lại không phải Prope.
- **Không dẫn pitch bằng "AI agent tự đề xuất cải tiến prompt".**
  **Đã có số liệu, không còn là phỏng đoán:** trong một thí nghiệm có đối chứng, các câu "cải tiến" chung chung làm **compliance của tác vụ RAG rơi từ 86.7% xuống 30%**, vì lệnh "hãy hữu ích và đầy đủ" khuyến khích model bịa thông tin không có trong nguồn. Tác hại còn **phụ thuộc chiều đo** — cùng một sửa đổi lại *cải thiện* khả năng tuân thủ hướng dẫn. **Không tồn tại "prompt tốt hơn" dạng vô hướng.**
  **Việc đúng của agent:** (1) **ingestion & lập bản đồ** — gom, trích, gom cụm, đặt tên cụm bằng ngôn ngữ người, soạn nháp trường ngữ nghĩa; (2) **lắp thẻ bằng chứng** cho người duyệt. Hỗ trợ soạn thảo cho marketer vẫn sống, nhưng ở dạng: soạn bản đầu từ ý định, luôn được kiểm bằng hợp đồng của chính tài sản đó, luôn ở dạng revision đề xuất để người dùng nhận hoặc bỏ.
  **Kỷ luật số lượng:** tối đa **một ứng viên đang chờ quyết cho mỗi prompt** — không bao giờ đổ ra một loạt biến thể.
- **Không phải nơi chat với model.** Không cạnh tranh với playground.
- **Không phải prompt marketplace.** Tài sản của tập đoàn, không phải chợ.
- **Không phải hệ thống deploy tự động.** Không bao giờ auto-release một prompt lên production.
- **Không phải sổ đăng ký quyền sở hữu trí tuệ.** Xem §7.2.
- **Không nằm trên hot path.** *(Xem §12 T3 — điều này vẫn đang mâu thuẫn với S7 và cần chốt.)*

---

## 7. Ranh giới cần nói cho đúng

### 7.1 Cơ sở pháp lý của HITL — đừng bán bằng lý do pháp lý

| | Thực tế |
|---|---|
| **EU AI Act** | Điều 12 (lưu vết), Điều 14 (giám sát của con người) — áp cho **hệ thống AI có rủi ro cao đang được triển khai**, không áp cho một lớp công cụ nội bộ quản lý prompt |
| **Luật AI Việt Nam 134/2025/QH15** | Thông qua 10/12/2025, hiệu lực 01/3/2026. Phân loại theo rủi ro. Nghĩa vụ "duy trì khả năng can thiệp của con người" áp cho **bên triển khai hệ thống rủi ro cao**, không áp cho nền tảng nội bộ |
| **Nghị định 142/2026/NĐ-CP** | Ban hành 30/4/2026, hiệu lực 01/5/2026. Miễn trừ áp cho hệ thống **không tương tác/cung cấp dịch vụ trực tiếp ra công chúng** — một register nội bộ nhiều khả năng rơi vào nhóm rủi ro thấp hoặc ngoài phạm vi |
| **Hai mốc thời gian khác nhau, đều có thật** | Luật cho **12 tháng** ân hạn với hệ thống đang vận hành (**18 tháng** cho y tế / giáo dục / tài chính); Nghị định đặt **hạn 60 ngày** (trước 30/6/2026) để nộp kế hoạch chuyển tiếp. **Đừng gộp hai cái này làm một.** |

**Vậy nói gì thay thế:**

> **HITL đứng trên cơ sở kiểm soát nội bộ, không phải luật:** người viết một thay đổi lên production không nên là người duy nhất phát hành nó. Đây là lập luận mà bộ phận kiểm soát nội bộ hiểu ngay.
> **Cộng thêm giá trị phòng ngừa:** các sản phẩm hạ nguồn của tập đoàn *có thể* rơi vào nhóm rủi ro trung bình/cao của Luật AI Việt Nam — và khi đó, hồ sơ duyệt kèm bằng chứng chính là thứ các team sản phẩm sẽ phải dựng lại từ đầu nếu không có. **Việc phân loại rủi ro là câu hỏi của từng sản phẩm, không bao giờ của register.**

> **[Thiếu — phải chốt trước pilot]** Quy định ngành cụ thể nào áp cho dữ liệu, audit và giám sát con người trong tập đoàn này. **Không được suy diễn rằng EU AI Act tự động áp dụng.**

### 7.2 Ranh giới của chính chữ "tài sản" (BR-09)

Brand tên là **Prope**, từ **property**. Đúng vì thế mà ranh giới này phải được nói to:

> **"Tài sản" / "property" là ẩn dụ sản phẩm về quyền sở hữu, trách nhiệm quản lý, quyền truy cập, nguồn gốc và giá trị vận hành.**
> **Prope KHÔNG xác lập quyền sở hữu trí tuệ, bản quyền, hay quyền theo hợp đồng.**

Cấm trong mọi copy: tuyên bố Prope xác lập sở hữu pháp lý · ngôn ngữ kiểu blockchain/token · "marketplace tài sản prompt".
Cấm trong mọi ẩn dụ: *sổ đỏ, chủ đất, người thuê, thế chấp, thuế tài sản, bất động sản.*
Được dùng: **Owner · Registry · Portfolio · Property history · Trusted revision · Grant access · Transfer ownership.**

Về mặt kế toán, cũng nên tự nói trước: know-how nội sinh theo IAS 38 phải ghi nhận vào chi phí, không lên bảng cân đối. **Không prompt nào lên balance sheet** — nói trước điều này chặn đứng câu hỏi khó nhất mà một giám đốc tài chính có thể đặt ra.

---

## 8. Thông điệp theo từng đối tượng

| Đối tượng | Câu mở đầu |
|---|---|
| **Prompt Owner — Minh + Toàn (Des & Mar)** | "Bạn không cần học prompt engineering. Điền vào chỗ trống, phần còn lại đã có người chuẩn hoá sẵn. Prompt của bạn vẫn là của bạn — private cho tới khi chính bạn grant access." |
| **Reviewer — Toàn (Manager)** | "Bạn sẽ biết chính xác revision nào đang chạy production, ai chịu trách nhiệm cho nó, và cái gì đã đổi — trong một màn hình, dưới hai phút." |
| **Developer — Quân (Dev)** | "Prompt ra khỏi code, nhưng chúng tôi **không đứng trên đường request của bạn**: revision đã Approved được đẩy xuống store bạn đang đọc. Đổi lại, hợp đồng kiểm tra của tài sản chạy như một bước CI trong repo của bạn — lỗi bị bắt ở pull request." |
| **Ban lãnh đạo** | "Tập đoàn đang trả tiền cho một tài sản mà không ai ghi sổ. Đây là sổ." |
| **Người dùng cá nhân** | "Prompt tốt nhất của bạn không nên biến mất trong lịch sử chat. Lưu nó, tìm lại nó, dùng lại nó — và giữ được cả lịch sử chỉnh sửa." |

---

## 9. Đối chiếu trực diện (dùng khi bị hỏi vặn)

| Bị hỏi | Trả lời một câu |
|---|---|
| "Sao không dùng Google Sheet / Notion?" | "Sheet không biết revision nào đang chạy production, không giữ được ai đã duyệt nó, và không restore được khi có sự cố." |
| "Sao không dùng Langfuse?" | "Langfuse là công cụ của developer, bắt đầu từ việc bạn phải instrument toàn bộ ứng dụng. Marketer của chúng tôi không làm được điều đó — mà họ mới là người viết phần lớn prompt." |
| "Sao không dùng Bedrock/Vertex có sẵn?" | "Vì nó chỉ thấy được những sản phẩm chạy trên chính nó. Tập đoàn có nhiều nhà cung cấp; chúng tôi là lớp duy nhất nhìn được toàn bộ." |
| "Sao không dùng Braintrust?" | "Braintrust bắt đầu từ giả định bạn đã có dataset và đã biết thế nào là 'tốt'. Chúng tôi bắt đầu từ giả định bạn chưa có gì cả." |
| "Cái này chỉ là Git cho prompt?" | "Git không cho marketer duyệt, và không trả lời được câu 'revision nào đang chạy production ngay lúc này'." |
| "Vậy cái gì thật sự không mua được?" | "Việc gom xuyên tài khoản, xuyên nhà cung cấp kèm chủ sở hữu/vòng đời/chi phí — và một đối tượng quyết định duyệt thật sự. Hai thứ đó không ai bán." |
| "Sao không để agent tự tối ưu prompt cho nhanh?" | "Vì cải tiến chung chung đã được đo là làm rơi compliance từ 86.7% xuống 30% ở tác vụ RAG. Không có 'prompt tốt hơn' chung chung — chỉ có tốt hơn cho một hợp đồng cụ thể." |
| "Eval của các bạn đảm bảo không giảm chất lượng chứ?" | "Không, và không ai làm được. Chúng tôi chặn cứng phần kiểm được bằng code, trình bày phần chủ quan cho người quyết, và theo dõi drift theo lịch — vì model có thể tự đổi mà không đổi version." |
| **"Prope có xác lập quyền sở hữu prompt cho tôi về mặt pháp lý không?"** | **"Không. 'Tài sản' ở đây là quyền sở hữu vận hành — ai chịu trách nhiệm, ai được truy cập, ai đã duyệt. Quyền sở hữu trí tuệ là việc của hợp đồng lao động và luật, không phải của chúng tôi."** |
| **"Bắt duyệt thì có làm chậm team không?"** | **"Một cấp, một reviewer, mục tiêu median dưới một ngày làm việc — và có đường break-glass cho trường hợp khẩn, kèm review bù trong 24h."** |
| **"Chúng tôi ngại đưa prompt thật lên."** | **"Private mặc định. Import không bao giờ tự publish, tự share hay tự release. Bạn phải chủ động grant access thì người khác mới thấy."** |

---

## 10. Tagline

**Đã chốt theo brand:**

> **Your prompt. Your property.** — *Prompt của bạn. Tài sản của bạn.*

**Câu category dùng khi giới thiệu sản phẩm:**

> Sổ tài sản prompt của tập đoàn — không phải thêm một dashboard AI ops.

**Câu mở màn khi demo (giữ từ v2, gắn với insight gốc):**

> Không còn Blind Box.

**Cấm dùng:** "The ultimate prompt management solution" · "Revolutionize your prompt workflow" · "Own your AI future" · "Marketplace tài sản prompt" · mọi câu ngụ ý Prope xác lập sở hữu pháp lý.

---

## 11. Rủi ro của định vị này

- **Rủi ro lớn nhất: phạm vi.** Registry + revision control + eval + agent + SDK là roadmap của 20 công ty đã gọi vốn. Bản demo phải chỉ gồm USP #1 + #2 (+ #3 ở mức hiển thị); phần còn lại là câu chuyện, không phải code.
- **"Tài sản" là từ trừu tượng.** Nếu không hiện được con số (Used by, lần dùng cuối, chi phí/tháng) thì nó chỉ là mỹ từ. RTB ở §5 là bắt buộc, không phải nice-to-have.
- **USP #1 phụ thuộc vào chất lượng ingestion.** Nếu gom ra kết quả nhiễu, toàn bộ định vị "bắt đầu từ hỗn loạn" sụp. Đây là hạng mục kỹ thuật rủi ro nhất và cần làm trước.
- **⚠️ Bất đối xứng bằng chứng.** Toàn bộ lập luận **ủng hộ** prompt register là do vendor/consultancy viết, và ở chương adoption thì hoàn toàn là suy luận tương tự. Lập luận **chống lại** thì vô tư và mạnh: một model registry lớn (MLflow) đã **công khai đảo ngược thiết kế vòng đời của chính nó**, CMDB mục rữa theo một cơ chế có tên, data catalog thất bại ở nhóm người dùng business. → **Đừng trình bày hai bên với cùng một mức độ tự tin.** Nói thẳng điều này ra sẽ *tăng* độ tin cậy, không giảm.
- **⚠️ Tiền lệ gần nhất với chính câu trả lời của ta đã từng thất bại.** Câu trả lời của ta cho vấn đề mục rữa là "tự sinh mọi trường". Nhưng CMDB có auto-discovery — và chính tài liệu của nhà cung cấp auto-discovery vẫn kê đơn **một data steward có tên cho mỗi lớp CI**, SLA khắc phục, và audit hàng quý, và nói decay "không phải rủi ro, mà là điều chắc chắn". → Tự sinh mua được **chi phí nhập liệu ban đầu**, không mua được **quyền sở hữu**. Cái còn lại là một **hàng đợi đối soát** (owner mồ côi, hash lệch, hợp đồng hết hạn, bản nhập chưa ai nhận), và tiêu chuẩn thiết kế là hàng đợi đó phải đủ nhỏ để **một người vận hành nền tảng là toàn bộ mô hình nhân sự**.
- **⚠️ Tiền đề chưa được đo cho trường hợp nội bộ.** Nghiên cứu thực nghiệm duy nhất, vô tư về vấn đề này đo trên **92 repo GitHub công khai**, không phải trên một tập đoàn. Con số đúng phải dùng: trùng lặp ngữ nghĩa **nội bộ 30.4% số repo** (và 38.5% ở cấp prompt). → Cách nói trung thực **và vẫn mạnh**: quần thể git đó *có* version control, code review, lịch sử tìm kiếm được — mà vẫn trùng lặp mức đó; một quần thể sống trong Sheet/Notion/Drive/chat **không có gì trong số đó**, nên khả năng rất cao là **ít nhất cũng tệ bằng**. Đây là suy luận, và phải nói rõ là suy luận.
- **⚠️ Bằng chứng khảo sát của chính ta cũng nhỏ và lệch.** Enterprise n=11, individual hợp lệ n=15, tuyển mẫu không ngẫu nhiên, tập trung ở vai trò software/product/AI-data. **Prompt Designer, business specialist và Approver bị thiếu đại diện** — tức là chính hai persona ưu tiên số 1 và số 2 của ta là nhóm ít bằng chứng nhất. Ý định trong khảo sát ≠ adoption thật.

### Cửa sổ thời gian

Nửa "một nhà cung cấp" của khoảng trống thị trường **sẽ đóng** trong một hai chu kỳ release — Langfuse đã có cách ghép nối. Nửa "xuyên nhà cung cấp" **sẽ không đóng**, vì nó đòi một vendor phải dựng view hạng nhất cho tài nguyên của đối thủ. **Hàng phòng thủ bền là lịch sử tích luỹ, không phải tính năng:** lịch sử ingestion và hồ sơ duyệt là dữ liệu riêng của tổ chức, không mang đi được.

Và về dài hạn: drift mang tính cấu trúc và đang tệ dần, vì nhà cung cấp hosted không công bố một đặc tả hành vi để bên triển khai kiểm tra. Một register chạy lại đúng bộ hợp đồng đó theo lịch là thứ duy nhất trả lời được **"hành vi production hiện tại có còn đúng cái ta đã duyệt không?"** — và **chính năng lực đó, không phải revision control, không phải agent, mới là thứ nền tảng này được định giá sau hai năm.**

---

## 12. ⚠️ Ba căng thẳng chưa giải quyết giữa định vị và nguồn chân lý

Tài liệu này và [`prope_source_of_truth.md`](prope_source_of_truth.md) chưa khớp ở ba chỗ. **Nguồn chân lý thắng khi mâu thuẫn** — nên ba mục dưới đây là câu hỏi cần chốt, không phải quyền tự do biên tập.

| # | Căng thẳng | Định vị nói | Nguồn chân lý nói | Đề xuất giải quyết |
|---|---|---|---|---|
| **T1** | **Phạm vi ingestion** | USP #1: *quét tự động* repo/Sheet/Notion/Drive/chat toàn tập đoàn, ra bản đồ hiện trạng < 2 phút | §16 MVP chỉ có **"add và import prompt"**; S4 là copy-paste, save selected text, import Sheets/Notion/repo/file có **preview trước khi đăng ký** — không có auto-scan | Giữ auto-discovery làm **câu chuyện định vị và mục tiêu Release 2+**; MVP demo bằng **import có chủ đích một repo + một Sheet thật**. Vẫn hiển thị "N đã phát hiện, M đã quản trị" — con số vẫn đúng với import. **Không hứa quét toàn tập đoàn ở pilot đầu.** |
| **T2** | **Chi phí là cổng chặn hay chỉ là số hiển thị** | USP #3 + RTB: cổng đỏ **chặn** một release ngay trên sân khấu | S9 Cost Alerts = **P2, impact 2, "defer and validate"**; §16 loại "advanced cost analytics" khỏi MVP. Phân tích nghiệp vụ FR-08 xếp P1 và yêu cầu **block/warn phải cấu hình được** | MVP: **hiển thị delta chi phí trong thẻ quyết định + cảnh báo (warn)**, chưa block cứng. Chính sách block bật được sau khi telemetry chứng minh độ chính xác. Nếu demo cần cảnh cổng đỏ, phải nói rõ đây là **policy cấu hình được**, không phải hành vi mặc định. |
| **T3** | **Prope có nằm trên request path không** | "Không nằm trên hot path" — chỉ đẩy revision đã Approved **xuống** runtime store của từng sản phẩm | S7 mô tả API/SDK **"retrieve approved revision only"** + environment aliases + version pinning — đọc theo nghĩa đen thì đây là *serving* | Chốt một mô hình trước khi code. Đề xuất: **push-down là mặc định**, API retrieval chỉ dùng ở build/deploy time và **bắt buộc có chiến lược fallback/cache** trước khi được phép nằm trên request path (NFR-05). Đây là điều kiện để giữ quyền phủ quyết của dev không bị kích hoạt. |

**Ngoài ba mục trên, còn hai điều kiện tiên quyết mà định vị không tự giải quyết được:**

- **Chưa có mô hình phân quyền, phân loại dữ liệu, retention hay chính sách xử lý nội dung nhạy cảm.** Phải chốt RBAC matrix và security baseline **trước khi import prompt thật** — đây là mức Critical trong phân tích nghiệp vụ §11, và cũng là rào cản adoption #2 trong khảo sát.
- **Repository hiện tại chưa hiện thực bất kỳ domain logic nào của Prope.** Không có registry, revision, RBAC, review, eval, cost control hay audit trail đang chạy. Mọi tuyên bố trong tài liệu này là **định vị**, không phải mô tả phần mềm đang tồn tại — khi demo, chỉ trình bày năng lực đã kiểm thử thật.

---

## 13. Checklist ngôn ngữ (áp cho mọi copy viết ra từ tài liệu này)

Trước khi duyệt bất kỳ đoạn copy nào:

- [ ] Dùng **Prope** — không bao giờ Promptrope, không `{{PRODUCT}}`, không "Sổ".
- [ ] Copy củng cố quyền sở hữu **của người dùng**, không phải của Prope.
- [ ] Nói rõ **cái gì được bảo vệ**, và nối quyền sở hữu với một lợi ích thật.
- [ ] Hành động rõ ràng **mà không cần dựa vào ẩn dụ**. Ẩn dụ tài sản chỉ dùng ở headline, onboarding, empty state, khoảnh khắc xác lập ownership, và Portfolio.
- [ ] Ngôn ngữ **literal** ở: phân quyền, phê duyệt, release production, hành động phá huỷ, tài liệu API.
- [ ] Dùng **revision** (không "version" trừ khi là *version ID* kỹ thuật), **restore** (không "rollback" với người không kỹ thuật), **grant access** (không "share publicly"), **trusted revision** (trạng thái hệ thống vẫn là **Approved**).
- [ ] Trạng thái giữ literal: **Draft · In review · Approved · In use · Retired**.
- [ ] Không đoạn nào có thể bị hiểu là **tuyên bố sở hữu pháp lý**.
- [ ] Không ẩn dụ bất động sản: *sổ đỏ, chủ đất, người thuê, thế chấp, thuế tài sản*.
- [ ] Không mô tả người dùng là bừa bộn hay quản lý kém.
- [ ] Không hứa eval "đảm bảo không giảm chất lượng".
- [ ] Giọng: điềm tĩnh, chắc chắn, tôn trọng — **bảo vệ hơn là quảng cáo, chính xác hơn là hoa mỹ**.

---

## Liên kết

- **Nguồn chân lý sản phẩm (thắng mọi tài liệu khác)** → [`docs/prope_source_of_truth.md`](prope_source_of_truth.md)
- **Phân tích nghiệp vụ, business rules, requirements** → [`docs/business-analysis.md`](business-analysis.md)
- **Tóm tắt 5 phút cho cả team** → [`docs/BRIEF.md`](BRIEF.md)
- **Nghiên cứu gốc, 116 nguồn** → [`docs/RESEARCH.vi.md`](RESEARCH.vi.md) · [`docs/RESEARCH.md`](RESEARCH.md)
- **Bối cảnh bài toán và ràng buộc gốc** → [`docs/research/runs/prompt-asset-register-solution-4fbe59/query.md`](research/runs/prompt-asset-register-solution-4fbe59/query.md)
