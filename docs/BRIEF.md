# BRIEF — Prope

> **Đọc trong 5 phút.** Đây là tài liệu ngắn nhất. Đọc nó trước, rồi mới đọc
> [`prope_source_of_truth.md`](prope_source_of_truth.md) (ngữ cảnh chuẩn) và
> [`positioning.md`](positioning.md) (định vị đầy đủ).
>
> | | |
> |---|---|
> | Trạng thái | **v2 — 2026-08-06** |
> | Tên sản phẩm | **Prope** *(đã chốt — thay cho `Sổ` ở v1 và `Promptrope` cũ)* |
> | Brand idea | **Prompt as property** — *Prompt là tài sản* |
> | Slogan | **Your prompt. Your property.** |
> | Nguồn chuẩn | [`prope_source_of_truth.md`](prope_source_of_truth.md) — **thắng mọi tài liệu khác khi mâu thuẫn** |
> | Nguồn khác | [`positioning.md`](positioning.md) v3 · [`business-analysis.md`](business-analysis.md) · [`RESEARCH.vi.md`](RESEARCH.vi.md) (116 nguồn) |
> | Stack | Python · FastAPI · LangGraph · PostgreSQL · Next.js · Docker |

---

## 1. Một câu

**Sổ tài sản prompt của tập đoàn — không phải thêm một dashboard AI ops.**

> **Your prompt. Your property.**
> Prope cho mỗi prompt một chủ sở hữu, một lịch sử revision, quyền truy cập rõ ràng, và một đường đi đáng tin cậy vào production.

---

## 2. Vấn đề (có số, không phải giả định)

Prompt của các sản phẩm AI trong tập đoàn nằm rải rác trong code, Google Sheet, Notion và
chat riêng của từng người.

**Khảo sát doanh nghiệp, n=11** *(định hướng, không đại diện thống kê — xem §11)*:

| Con số | Ý nghĩa |
|---|---|
| **10/11** lưu prompt trong lịch sử chat · **~3 nơi lưu / người** · **0/11** dùng công cụ chuyên dụng | Đối thủ thật là Sheet + Notion + chat, không phải Langfuse |
| **11/11** không tìm/nhận ra được prompt cần · **11/11** không biết revision mới nhất · **11/11** thấy các thành viên dùng prompt khác nhau cho cùng một việc | Đây là nỗi đau phổ quát — và là P0 |
| **9/11** không biết ai là chủ sở hữu | Không có accountability |
| **8/11** output không nhất quán · **7/11** phải làm lại · **5/11** không xác định được prompt gây lỗi · **4/11** phát hiện lỗi sau khi release | Hậu quả vận hành thật |
| **0/11** có quy trình phê duyệt chính thức | Không có gì để thay thế — chỉ có chỗ trống để lấp |
| **2/11** gặp chi phí tăng bất ngờ | ⚠️ Chi phí là nỗi đau **ít được cảm nhận nhất**. Đừng dẫn pitch bằng nó. |

**Khảo sát cá nhân, hợp lệ n=15:** 13/15 tạo nhiều prompt gần giống nhau · 13/15 sửa mà không
giữ bản cũ · 12/15 không nhớ bản nào chạy tốt nhất · 9/15 không tìm lại được.

**Trùng lặp âm thầm.** Đo trên 92 repo GitHub công khai: **30.4% repo có prompt trùng lặp
ngữ nghĩa nội bộ**, và **38.5% ở cấp prompt**. Đó là quần thể *có* version control, code
review, lịch sử tìm kiếm được. Quần thể sống trong Sheet/Notion/chat không có gì trong số
đó — nhiều khả năng còn tệ hơn. *(Đây là suy luận. Phải nói rõ là suy luận.)*

**Vấn đề gốc — nói cho đúng:**

> Các đội đang tạo ra tài sản prompt có giá trị, nhưng thiếu một hệ thống đáng tin để xác lập
> quyền sở hữu, giữ lịch sử, kiểm soát truy cập và đưa nó vào việc một cách an toàn.

❌ **Không được rút gọn thành** "người dùng cần một chỗ để lưu prompt". Vấn đề sâu hơn là
**mất ownership, mất provenance, mất niềm tin**.

---

## 3. Cho ai (thứ tự ưu tiên có chủ đích)

| # | Vai chuẩn | Persona | Họ cần gì | Vì sao xếp ở đây |
|---|---|---|---|---|
| 1 | **Prompt Owner** | Minh + Toàn — Designer & Marketer | Đưa prompt vào không cần code, xác lập ownership, tìm lại, giữ revision, kiểm soát truy cập | **Người dùng số 1.** Mọi đối thủ đều xếp họ hạng cuối. Đây là chỗ ta thắng. |
| 2 | **Reviewer / Approver** | Toàn — Manager | Duyệt trong 2 phút, biết cái gì đã đổi, ai chịu trách nhiệm, tốn bao nhiêu | Người ra quyết định, người ký |
| 3 | **Developer / AI Engineer** | Quân — Dev | Chỉ lấy revision đã Approved, pin version ID, release và restore an toàn | **Số 2, không phải số 1** — nhưng có **quyền phủ quyết** |

> ⚠️ Dev ít ảnh hưởng nhất tới việc marketer có dùng hay không — **cho tới lúc** Prope gây sự cố
> production. Lúc đó dev cấm dùng và công cụ của marketer chết theo. Vì vậy **Prope không nằm
> trên hot path**: đẩy revision đã Approved xuống runtime store của từng sản phẩm.
> *(Điều này còn mâu thuẫn với S7 trong nguồn chân lý — xem §12 T3 của `positioning.md`.)*

### Chế độ cá nhân — một câu chuyện khác, không phải bản rút gọn

Cá nhân cần đúng bốn động từ: **Lưu → Tìm → Dùng lại → Giữ lịch sử.**
**Không phơi toàn bộ mô hình quản trị ra làm trải nghiệm cá nhân mặc định.**
Ngôn ngữ cũng khác: *prompt của bạn, công việc của bạn, giữ lại, tìm lại* — không phải
*provenance, access control, release*.

---

## 4. Ta đang thay thế cái gì

**Không phải Langfuse.** Là **Google Sheet + Notion + Drive + tài khoản dùng chung + một đoạn
chat có sẵn prompt**. (0/11 người khảo sát dùng công cụ chuyên dụng nào.)

> **Tiêu chí thắng thua:** không phải "ngang tính năng với Langfuse", mà là
> **"được dùng nhiều hơn Google Sheet trong chính tập đoàn này"**.
> Mọi tính năng phải được chấm điểm theo đúng thước đo đó.

---

## 5. Xây cái gì — 3 trụ cột

Ba trụ cột không phải ba tính năng. Chúng là **ba thời điểm cuốn sổ tự ghi chính nó.**
Thứ tự dưới đây khớp với priority matrix của nguồn chân lý (§15).

### ① Bắt đầu từ hỗn loạn, không bắt đầu từ trang trắng · *S1 + S4, P0*
Import từ repo + Sheet + Notion + file export → trích xuất → gom cụm bản gần trùng →
trả về bản đồ hiện trạng trong **dưới 2 phút**.

Hiển thị theo **hai quần thể**, không phải một con số:
> ❌ "Tập đoàn có 213 prompt."
> ✅ **"412 đã phát hiện, 38 đã được quản trị."**

Prompt nhập hàng loạt rơi vào trạng thái **chưa được nhận (ungoverned)** và bị loại khỏi mọi
thống kê quản trị. Trường ngữ nghĩa để **trống**, không để AI đoán. Một cuốn sổ phân biệt được
cái nó *biết* với cái nó chỉ đang *giữ* là cuốn sổ duy nhất đáng tin.

**Bất di bất dịch (BR-01):** **private mặc định · không auto-publish · không auto-share ·
không auto-release.** Rào cản adoption số 1 trong khảo sát là "ngại chia sẻ prompt cá nhân".

> ⚠️ MVP là **import có chủ đích**, không phải quét tự động toàn tập đoàn. Auto-discovery là
> câu chuyện Release 2+. Xem `positioning.md` §12 T1.

### ② HITL mà người duyệt quyết được trong 2 phút · *S6, P1*
> **"Đối tượng quyết định duyệt" (approval-decision object) — không nhà cung cấp nào bán thứ này.**

Ở Langfuse, PromptLayer, Bedrock, Vertex, "promote" chỉ là **một lượt ghi có phân quyền vào một
cái nhãn**: không có trạng thái chờ duyệt, không có hồ sơ bằng chứng, không tách người đề xuất
khỏi người quyết, không có đường từ chối. Chính Langfuse ghi trong bảng năng lực của họ rằng
multi-step approval workflow là *Composed*, không phải *Native*. Và **0/11** đội khảo sát có
quy trình duyệt chính thức — không có gì để thay thế, chỉ có chỗ trống để lấp.

Nó là **trigger ghi** cho chủ sở hữu, trusted revision, trạng thái vòng đời và cả hai
trường ngữ nghĩa — trong **một hành động duy nhất**.

**Kỷ luật chống bureaucracy:** **một cấp, một reviewer.** Không multi-level approval trong MVP.
Mục tiêu: median review **dưới một ngày làm việc**, ≥70% báo không bị chậm đáng kể.
Bắt buộc có **break-glass**: release khẩn được phép, kèm log lý do một dòng và task review bù
trong 24h — nếu không, người ta sẽ đi vòng qua cổng vĩnh viễn.

### ③ Chi phí là cổng chặn, không phải biểu đồ · *S9, P2 — "defer and validate"*
> "Bản này tốt hơn 3% nhưng đắt hơn 40% — bạn vẫn muốn release chứ?"

**KHÔNG đo token của prompt.** Có case ghi nhận cắt ~17% input token mà **tổng chi phí phiên
tăng ~67%** — model phải trả tiền suy luận lại phần ngữ cảnh bị cắt. Đo **chi phí trên mỗi tác
vụ hoàn thành thành công**, tính cả retry.

> ⚠️ **Trụ cột yếu nhất về bằng chứng: chỉ 2/11 từng gặp chi phí tăng bất ngờ**, và S9 nằm ở P2.
> MVP: **hiển thị delta + cảnh báo**, chưa block cứng. Chính sách block phải **cấu hình được**.
> Xem `positioning.md` §12 T2.

---

## 6. Luồng cốt lõi và MVP (nguồn chân lý §16)

```text
Đưa prompt vào Prope
→ Gán owner và access
→ Tạo revision
→ Review thay đổi + bằng chứng
→ Approve trusted revision
→ Release để đưa vào dùng
→ Restore revision cũ nếu cần
```

**Có trong MVP:** add/import prompt · registry + search · Owner · revision history · diff ·
trạng thái Draft/In review/Approved · access private & team · **một** reviewer ·
approve hoặc request changes · property history cơ bản · API/export đơn giản cho revision đã Approved.

**KHÔNG có trong MVP:** multi-level approval · semantic clustering nâng cao · cost analytics
nâng cao · SDK đầy đủ · environment orchestration đầy đủ · policy engine phức tạp ·
full observability · workflow pháp lý về sở hữu trí tuệ.

**Từ vựng bắt buộc:** **revision** (không "version"), **restore** (không "rollback"),
**grant access** (không "share"), **release** (không "publish"), **trusted revision**
(trạng thái hệ thống vẫn là **Approved**). Trạng thái giữ literal:
**Draft · In review · Approved · In use · Retired**.

---

## 7. Bài kiểm tra ngày-90 (định nghĩa "tài sản" theo cách có thể bị bác bỏ)

> Lấy ngẫu nhiên 20 prompt vào ngày thứ 90. Kiểm tra 4 trường:
> **chủ sở hữu · trusted revision + trạng thái (có đường Retired) · Used by · chi phí.**
> Nếu bất kỳ trường nào trống, cũ, hoặc phải có người *nhớ* để cập nhật — đây là một database
> có cái tên đắt tiền, và marketer quay lại Google Sheet là đúng.

> ⚠️ Trường **chi phí** phụ thuộc telemetry (P2). Ở MVP, bài kiểm tra chạy với **3 trường đầu**.
> Đừng hứa trường thứ tư trong pilot đầu tiên rồi trượt nó.

**Luật thiết kế rút ra — áp cho mọi feature:**

> *Mọi trường vận hành phải được sinh ra từ một hành động ai đó vốn dĩ đã làm.*
> Chủ sở hữu ← ai bấm Approve. Trusted revision ← chính hành động Approve. Used by ← API/SDK gọi.
> Chi phí ← telemetry.
>
> Trường duy nhất không tự sinh được — *prompt này để làm gì* — được thu thập **bên trong**
> đúng bước review mà ta vốn đã bắt buộc.

**Nếu một feature yêu cầu người dùng nhớ cập nhật một trường, feature đó sai thiết kế.**

---

## 8. KHÔNG làm gì (đọc kỹ — đây là hàng rào chống chết vì scope)

- ❌ **Không làm tracing/observability.** Langfuse miễn phí và làm tốt hơn. Tích hợp, không cạnh tranh.
- ❌ **Không chỉ là thư viện prompt / kho template.** Bỏ ownership + revision + trusted path thì không còn là Prope.
- ❌ **Không dẫn pitch bằng "AI agent tự đề xuất cải tiến prompt".** Trong một thí nghiệm có
  đối chứng, các câu "cải tiến" chung chung làm **compliance của tác vụ RAG rơi từ 86.7% xuống
  30%**. Không tồn tại "prompt tốt hơn" dạng vô hướng.
  → **Việc đúng của agent:** (1) ingestion & lập bản đồ, (2) lắp thẻ bằng chứng cho người duyệt.
  → **Kỷ luật số lượng:** tối đa **một ứng viên đang chờ quyết cho mỗi prompt**.
- ❌ **Không phải nơi chat với model.** Không cạnh tranh với playground.
- ❌ **Không phải prompt marketplace.**
- ❌ **Không auto-release.** Human approval là bắt buộc trước production (BR-04).
- ❌ **Không nằm trên hot path.** Đẩy xuống, không đứng giữa.
- ❌ **Không hứa "eval đảm bảo không giảm chất lượng".** Không ai làm được — chặn phần kiểm được
  bằng code, trình bày phần chủ quan, theo dõi drift theo lịch.
- ❌ **Không tuyên bố Prope xác lập quyền sở hữu trí tuệ.** Xem §9.

---

## 9. Hai ranh giới phải nói cho đúng

### 9.1 "Tài sản" là ẩn dụ sản phẩm, không phải quyền pháp lý (BR-09)

Brand tên là **Prope**, từ **property** — chính vì thế ranh giới này phải được nói to:

> "Tài sản" nói về **quyền sở hữu vận hành**: ai chịu trách nhiệm, ai được truy cập, cái gì đã đổi,
> ai đã duyệt. **Prope không xác lập quyền sở hữu trí tuệ, bản quyền hay quyền hợp đồng.**

Cấm ẩn dụ bất động sản: *sổ đỏ · chủ đất · người thuê · thế chấp · thuế tài sản*.
Được dùng: **Owner · Registry · Portfolio · Property history · Trusted revision · Grant access ·
Transfer ownership**.

### 9.2 HITL — đừng bán bằng lý do pháp lý

Không EU AI Act lẫn Luật AI Việt Nam 134/2025/QH15 bắt buộc người duyệt cho một **nền tảng nội
bộ**. Nghị định 142/2026/NĐ-CP miễn trừ hệ thống không cung cấp dịch vụ trực tiếp ra công chúng.
Bán bằng lý do pháp lý sẽ không qua được vòng review của legal.

**Nói thế này thay thế:**
> HITL đứng trên cơ sở **kiểm soát nội bộ**: người viết một thay đổi lên production không nên
> là người duy nhất phát hành nó. Đây là lập luận mà bộ phận kiểm soát nội bộ hiểu ngay.

Chi tiết đầy đủ (kèm hai mốc thời gian khác nhau, đều có thật): [`positioning.md`](positioning.md) §7.

---

## 10. Định nghĩa thành công cho demo day

| # | Bằng chứng phải diễn được trên sân khấu | Đo bằng |
|---|---|---|
| 1 | Import một repo thật + một Sheet thật → bản đồ hiện trạng | < 2 phút, hiện **"N đã phát hiện, M đã quản trị"** |
| 2 | Một người **không phải dev** tạo & submit một revision | 0 dòng code |
| 3 | Tìm ra trusted revision của một prompt | < 30 giây |
| 4 | Duyệt trong 2 phút | Một màn hình: diff hệ quả + 3 ví dụ output lệch nhau + delta chi phí + blast radius |
| 5 | Từ 1 output lỗi ngoài production → truy ngược ra revision + model + biến | < 3 cú click |
| 6 | Restore | Con trỏ production quay về revision đã Approved trước đó, có audit event, **< 5 phút** |
| 7 | Cảnh báo delta chi phí **trên mỗi tác vụ thành công** *(nếu telemetry kịp)* | Cảnh báo hiện ra trước quyết định — nói rõ block là **policy cấu hình được** |

Đối chiếu với 10 deliverables của BTC: [`docs/guide/deliverables/checklist.md`](guide/deliverables/checklist.md).

---

## 11. Ba công cụ tự chứng minh sai (ship kèm sản phẩm)

Định vị này có thể sai. Ta nên là người phát hiện ra trước.

1. **Nếu lần import đầu tiên cho tỷ lệ trùng lặp thấp hơn nhiều so với 30.4%** → tiền đề gốc yếu,
   phải rescope quanh revision control thay vì discovery.
2. **Nếu tỷ lệ sửa trường "mục đích" gần bằng 0 trong pilot** → tầng ngữ nghĩa không đáng tin,
   và bước review đang bị làm cho có.
3. **Nếu người dùng export bảng ra Google Sheet trong tuần đầu** → view trong Registry chưa trả lời
   được câu hỏi thật của họ. Đây là dấu hiệu cảnh báo kinh điển của mọi hệ thống bị bỏ rơi.

Cả ba đều phải **được instrument sẵn**, không phải khảo sát thủ công.

---

## 12. Rủi ro lớn nhất, xếp theo mức độ

| # | Rủi ro | Đối phó |
|---|---|---|
| 1 | **Chưa có mô hình phân quyền, phân loại dữ liệu, retention, chính sách nội dung nhạy cảm.** Đây là mức **Critical** trong phân tích nghiệp vụ, và là rào cản adoption #2 trong khảo sát. | Chốt **RBAC matrix + security baseline trước khi import prompt thật**. Không thương lượng. |
| 2 | **Scope.** Registry + revision + eval + agent + SDK là roadmap của 20 công ty đã gọi vốn. | Demo **chỉ** gồm 3 trụ cột, và trụ cột ③ ở mức hiển thị. Phần còn lại là câu chuyện, không phải code. |
| 3 | **Chất lượng ingestion.** Nếu gom ra nhiễu, toàn bộ định vị "bắt đầu từ hỗn loạn" sụp. | Hạng mục kỹ thuật rủi ro nhất → **làm trước tiên, tuần 1**. |
| 4 | **"Tài sản" là từ trừu tượng.** Không hiện được con số thì chỉ là mỹ từ. | Bài kiểm tra ngày-90 (§7) là tiêu chí nghiệm thu, không phải nice-to-have. |
| 5 | **Bất đối xứng bằng chứng.** Lập luận ủng hộ prompt register đều do vendor viết; lập luận chống lại thì vô tư và mạnh (MLflow đã đảo ngược thiết kế vòng đời của chính nó; CMDB mục rữa; data catalog thất bại ở nhóm business). | **Đừng trình bày hai bên với cùng mức độ tự tin.** Nói thẳng ra sẽ *tăng* độ tin cậy. |
| 6 | **Tiền lệ gần nhất với chính câu trả lời của ta đã từng thất bại.** CMDB *có* auto-discovery — và tài liệu của chính nhà cung cấp vẫn kê đơn một data steward có tên cho mỗi lớp CI. Tự sinh mua được **chi phí nhập liệu ban đầu**, không mua được **quyền sở hữu**. | Cái còn lại là một **hàng đợi đối soát** (owner mồ côi, hash lệch, bản nhập chưa ai nhận), và tiêu chuẩn thiết kế là hàng đợi đó phải đủ nhỏ để **một người vận hành là toàn bộ mô hình nhân sự**. |
| 7 | **Bằng chứng khảo sát của chính ta nhỏ và lệch.** n=11 / n=15, tuyển mẫu không ngẫu nhiên, tập trung ở vai trò software/product/AI-data. **Prompt Designer, business specialist và Approver bị thiếu đại diện** — đúng hai persona ưu tiên #1 và #2. | Coi mọi số liệu là **định hướng**. Bước kiểm chứng tiếp theo: 5–8 interview + prototype test + một pilot đội thật. |
| 8 | **USP ① mới nhưng chưa được chứng minh.** Không nguồn nào cho thấy đối thủ làm được — đó là bằng chứng về *tính mới*, không phải *tính hiệu quả*. | Nói thật. Đo bằng công cụ tự chứng minh sai #1. |
| 9 | **Repo hiện tại chưa có domain logic nào của Prope.** Không có registry, revision, RBAC, review, eval, cost control hay audit trail đang chạy. | Tách rõ tài liệu discovery khỏi tuyên bố đã hiện thực. **Chỉ demo năng lực đã kiểm thử thật.** |

### Cửa sổ thời gian

Nửa "một nhà cung cấp" của khoảng trống thị trường **sẽ đóng** trong một hai chu kỳ release —
Langfuse đã có cách ghép nối. Nửa "xuyên nhà cung cấp" **sẽ không đóng**, vì nó đòi một vendor
phải dựng view hạng nhất cho tài nguyên của đối thủ.

**Hàng phòng thủ bền là lịch sử tích luỹ, không phải tính năng:** lịch sử ingestion và hồ sơ
duyệt là dữ liệu riêng của tổ chức, không mang đi được.

---

## 13. Câu hỏi còn mở (cần chốt trước khi code)

| # | Câu hỏi | Ai chốt | Hạn |
|---|---|---|---|
| 1 | **RBAC matrix, phân loại dữ liệu, retention, xử lý nội dung nhạy cảm** | Sponsor + security | **Trước khi import prompt thật** |
| 2 | Ai là sponsor/buyer và đội pilot đầu tiên? | Cả team | Tuần 1 |
| 3 | Repo + Sheet nào dùng cho demo import thật? Cần dữ liệu thật, không phải seed data | Cả team | Tuần 1 |
| 4 | Approval gắn với **revision**, **release**, hay cả hai? Emergency restore có bypass không? | Product owner | Tuần 1 |
| 5 | Owner là một người hay một team? Có nhiều steward không? Transfer và khi owner rời tổ chức xử lý ra sao? | Product owner | Tuần 1 |
| 6 | Nguồn import nào làm trước — Sheets, Notion, hay repo? Có làm Notion connector trong MVP không? | Tech lead | Tuần 1 |
| 7 | Prope có nằm trên request path không (push-down vs. API retrieval)? Fallback ra sao? | Tech lead + dev | Tuần 2, trước khi hứa SDK |
| 8 | Loại task nào có eval deterministic? Ai sở hữu eval contract và ngưỡng? | Domain owner + AI engineer | Tuần 2 |
| 9 | Ai đóng vai Approver trong video demo | Cả team | Tuần 3 |
| 10 | Điền mốc thời gian thật của BTC vào kế hoạch | PM | Ngay |

*(Câu hỏi "chốt tên sản phẩm" ở v1 đã đóng: tên là **Prope**.)*

---

## Liên kết

- **Nguồn chân lý sản phẩm (thắng mọi tài liệu khác)** → [`docs/prope_source_of_truth.md`](prope_source_of_truth.md)
- **Định vị & USP đầy đủ** → [`docs/positioning.md`](positioning.md)
- **Phân tích nghiệp vụ, business rules, requirements** → [`docs/business-analysis.md`](business-analysis.md)
- **Nghiên cứu gốc, 116 nguồn** → [`docs/RESEARCH.vi.md`](RESEARCH.vi.md) · [`docs/RESEARCH.md`](RESEARCH.md)
- **Yêu cầu nộp bài của BTC** → [`docs/guide/deliverables/checklist.md`](guide/deliverables/checklist.md)

> **Chưa tồn tại:** `PRD.md` và `WIREFRAME.md` (v1 của tài liệu này có trỏ tới). Yêu cầu chức năng
> hiện nằm ở [`business-analysis.md`](business-analysis.md) §9 (FR-01…FR-10, NFR-01…NFR-05);
> backlog giải pháp và roadmap nằm ở [`prope_source_of_truth.md`](prope_source_of_truth.md) §14–17.
