# Positioning & USP

> Trạng thái: draft v1 — 2026-08-02
> Placeholder `{{PRODUCT}}` = tên sản phẩm (chưa chốt). Find-replace khi có tên chính thức.
> Nguồn: problem statement gốc + research personas (Quân/Dev, Toàn/Manager, Minh+Toàn/Des&Mar) + competitive landscape (xem `docs/product/competitive-landscape.md` khi có).

---

## 1. Positioning statement (bản chính)

> **Cho** các đội sản phẩm trong tập đoàn — nơi prompt của sản phẩm AI đang nằm rải rác trong code, Google Sheet, Notion và chat cá nhân,
> **{{PRODUCT}} là** sổ tài sản prompt (prompt asset register) dùng chung cho toàn tập đoàn,
> **giúp** biến prompt từ một đoạn text cá nhân thành tài sản có chủ sở hữu, có lịch sử, có bằng chứng chất lượng và có chi phí đo được — trước khi nó được phát hành lên production,
> **khác với** các nền tảng LLMOps hiện có (Langfuse, LangSmith, Braintrust, Bedrock/Vertex Prompt Management) vốn được thiết kế cho developer và chỉ biết đến những prompt đã nằm sẵn trong hệ thống,
> **{{PRODUCT}} bắt đầu từ chính sự hỗn loạn có thật** — tự phát hiện và gom prompt đang rải rác khắp nơi — và cho người **không phải developer** (marketer, designer, PM) dùng được ngay từ ngày đầu.

### One-liner

**Sổ tài sản prompt của tập đoàn — không phải thêm một dashboard AI ops.**
*(EN: The company's prompt asset register — not another AI ops dashboard.)*

### Elevator (30 giây)

> Mọi công ty làm sản phẩm AI đều có một tài sản vô hình đang bị thất thoát: prompt. Chúng nằm rải rác trong code, Sheet, Notion, chat riêng của từng người. Không ai biết bản nào đang chạy production, không ai rollback được, và khi một người nghỉ việc thì prompt tốt nhất của họ biến mất theo.
> {{PRODUCT}} gom toàn bộ số prompt đó về một nơi, gắn cho mỗi prompt một chủ sở hữu, một lịch sử, một điểm chất lượng và một con số chi phí — rồi bắt mọi thay đổi phải chứng minh bằng bằng chứng trước khi được duyệt lên production.

---

## 2. Category

Chúng ta **tự định nghĩa category**, không nhảy vào category có sẵn:

| | |
|---|---|
| ❌ Không phải | LLM observability / tracing platform |
| ❌ Không phải | Prompt playground / prompt marketplace |
| ❌ Không phải | Eval framework |
| ✅ Là | **Prompt Asset Register** — sổ tài sản + lớp quản trị phát hành prompt cho tổ chức |

**Vì sao tự định nghĩa category:** nếu vào category "LLMOps observability", ta phải đấu tay đôi với Langfuse (open-source, miễn phí, 30K sao) và thua ngay ở bảng feature. Category "tài sản của tổ chức" là category ta viết luật chơi: đơn vị đo không phải trace/span, mà là *chủ sở hữu, vòng đời, chất lượng, chi phí*.

---

## 3. Đối tượng & frame of reference

### Người dùng chính (thứ tự ưu tiên có chủ đích)

1. **Minh + Toàn — Designer & Marketer.** Không biết code, không cài SDK, "lười". **Đây là người dùng số 1.** Mọi đối thủ đều xếp họ ở hạng cuối.
2. **Toàn — Manager.** Người phải duyệt promote, chịu trách nhiệm chất lượng và chi phí. Cần quyết trong 2 phút.
3. **Quân — Dev.** Người tiêu thụ prompt qua API/SDK và không muốn mất kiểm soát. **Người dùng số 2, không phải số 1.**

### Ta đang thay thế cái gì (frame of reference thật)

Không phải Langfuse. Là **Google Sheet + Notion + Drive + tài khoản dùng chung + một đoạn chat có sẵn prompt**.

> **Tiêu chí thắng thua:** không phải "ngang tính năng với Langfuse", mà là **"được dùng nhiều hơn Google Sheet trong chính tập đoàn này"**.
> Mọi tính năng phải được chấm điểm theo thước đo đó.

---

## 4. USP — 3 trụ cột

Mỗi trụ cột phải trả lời được: *đối thủ không làm được, hoặc không thèm làm.*

### USP #1 — Bắt đầu từ hỗn loạn, không bắt đầu từ trang trắng
**"Có giá trị trong 10 phút đầu, trước khi bạn di chuyển bất cứ thứ gì."**

Quét repo, Google Sheet, Notion, Drive, chat export → trích xuất mọi prompt → gom cụm bản gần trùng → trả về bản đồ hiện trạng:
> *"Tập đoàn đang có 213 prompt. 68 bản gần trùng nhau. 41 bản đang chạy trong code production. 12 bản 6 tháng không ai đụng."*

**Vì sao đối thủ không có:** toàn bộ Tier 1–4 chỉ biết đến prompt **đã nằm trong hệ thống của họ**. Tất cả đều yêu cầu bạn phải ngăn nắp *trước khi* nhận được giá trị. Đây là lý do họ liên tục thua Google Sheet.
**Liên kết HMW:** I-1, I-2, I-4.

### USP #2 — Chi phí là cổng chặn, không phải biểu đồ
**"Bản này tốt hơn 3% nhưng đắt hơn 40% — bạn vẫn muốn phát hành chứ?"**

Delta token/chi phí hiện ngay trong lúc gõ, và nằm trên thẻ quyết định promote như một tín hiệu bắt buộc, kèm quy chi phí về từng team/sản phẩm.

**Vì sao đối thủ không có:** các nền tảng observability báo cáo chi phí **sau khi đã tiêu**. Rất ít nơi biến nó thành điều kiện phát hành **trước khi** merge.
**Liên kết HMW:** G-1, G-2, G-4. Trực tiếp đáp ràng buộc "cảnh báo thay đổi làm tăng token/chi phí".

### USP #3 — HITL mà người duyệt quyết được trong 2 phút
**"Một màn hình. Duyệt hoặc không."**

Thẻ quyết định gồm: diff bằng ngôn ngữ hệ quả (không phải diff text), delta chất lượng từ eval hồi quy, delta chi phí, blast radius (những sản phẩm nào đang tiêu thụ prompt này), và khuyến nghị.

**Vì sao đối thủ không có:** RBAC + approval queue thì ai cũng có. Không ai làm cho **2 phút của người duyệt** trở nên dễ chịu — và họ đều thiết kế cho người duyệt là engineer, trong khi người duyệt của ta là manager.
**Liên kết HMW:** F-2, F-4, D-4.

### Hai USP hỗ trợ (làm cho 3 trụ cột trên khả thi)

- **Eval tự mồi từ production.** Test-case sinh tự động từ traffic thật + phản hồi 1 cú nhấn của người dùng cuối. Giải bài toán con-gà-quả-trứng khiến eval hồi quy bắt buộc trở nên bất khả thi ở mọi nơi khác.
- **Là một lớp, không phải một sự thay thế.** Đồng bộ version xuống Bedrock/Vertex/runtime mà từng team đang dùng, và kéo trace ngược về qua OTel. Đây là câu trả lời cho *"sao không dùng luôn Bedrock?"* — vì Bedrock chỉ thấy được sản phẩm chạy trên Bedrock, còn ta thấy toàn tập đoàn.

---

## 5. Reason to believe

| Tuyên bố | Bằng chứng cần có ở demo |
|---|---|
| Biến prompt thành tài sản | Mỗi prompt có owner, version, số sản phẩm đang dùng, chi phí/tháng, lần dùng cuối |
| Bắt đầu từ hỗn loạn | Demo scan một repo + một Sheet thật, ra bản đồ hiện trạng trong < 2 phút |
| Không còn Blind Box | Từ 1 output lỗi ngoài production → truy ngược ra version + model + biến đã sinh ra nó |
| Chi phí có người chịu trách nhiệm | Cảnh báo delta chi phí chặn được một promote ngay trên sân khấu |
| Người không biết code dùng được | Cho một người không phải dev tạo & đề xuất một prompt trong demo, không dòng code nào |

---

## 6. Anti-positioning — những gì {{PRODUCT}} KHÔNG làm

Nói rõ ra để tránh bị so sánh sai và tránh scope creep:

- **Không làm tracing/observability.** Langfuse miễn phí và làm tốt hơn. Ta tích hợp, không cạnh tranh.
- **Không dẫn pitch bằng "AI agent tự đề xuất cải tiến prompt".** Braintrust Loop, PromptLayer, Bedrock đều đã có. Đây là *tính năng*, không phải USP. Nó nằm ở tầng 2 của thông điệp.
- **Không phải nơi chat với model.** Không cạnh tranh với playground.
- **Không phải prompt marketplace.** Tài sản của tập đoàn, không phải chợ.

---

## 7. Thông điệp theo từng persona

| Persona | Câu mở đầu |
|---|---|
| **Minh + Toàn (Des & Mar)** | "Bạn không cần học prompt engineering. Điền vào chỗ trống, phần còn lại đã có người chuẩn hóa sẵn." |
| **Toàn (Manager)** | "Bạn sẽ biết chính xác bản nào đang chạy production, nó tốn bao nhiêu, và ai chịu trách nhiệm cho nó." |
| **Quân (Dev)** | "Prompt ra khỏi code, nhưng bạn không mất kiểm soát: version cố định, gọi qua SDK, có cache khi nền tảng chết." |
| **Ban lãnh đạo** | "Tập đoàn đang trả tiền cho một tài sản mà không ai ghi sổ. Đây là sổ." |

---

## 8. Đối chiếu trực diện (dùng khi bị hỏi vặn)

| Bị hỏi | Trả lời một câu |
|---|---|
| "Sao không dùng Google Sheet / Notion?" | "Sheet không biết bản nào đang chạy production, và không chặn được một thay đổi làm tăng 40% chi phí." |
| "Sao không dùng Langfuse?" | "Langfuse là công cụ của developer, bắt đầu từ việc bạn phải instrument toàn bộ ứng dụng. Marketer của chúng tôi không làm được điều đó — mà họ mới là người viết phần lớn prompt." |
| "Sao không dùng Bedrock/Vertex có sẵn?" | "Vì nó chỉ thấy được những sản phẩm chạy trên chính nó. Tập đoàn có nhiều nhà cung cấp; chúng tôi là lớp duy nhất nhìn được toàn bộ." |
| "Sao không dùng Braintrust?" | "Braintrust bắt đầu từ giả định bạn đã có dataset và đã biết thế nào là 'tốt'. Chúng tôi bắt đầu từ giả định bạn chưa có gì cả." |
| "Cái này chỉ là Git cho prompt?" | "Git không biết một commit làm tăng chi phí bao nhiêu, và không cho marketer duyệt." |

---

## 9. Tagline — các phương án đang cân nhắc

1. **Sổ tài sản prompt của tập đoàn.** *(an toàn nhất, đúng category)*
2. **Prompt là tài sản. Hãy ghi sổ nó.**
3. **Không còn Blind Box.** *(mạnh, gắn với insight gốc trong research)*
4. **Từ Google Sheet đến sổ tài sản.**

→ Đề xuất chốt: **#1 làm định vị chính thức, #3 làm câu mở màn khi demo.**

---

## 10. Rủi ro của định vị này

- **Rủi ro lớn nhất: phạm vi.** Registry + versioning + eval + agent + SDK là roadmap của 20 công ty đã gọi vốn. Bản demo phải chỉ gồm USP #1 + #2 + #3; phần còn lại là câu chuyện, không phải code.
- **"Tài sản" là từ trừu tượng.** Nếu không hiện được con số (chi phí/tháng, số sản phẩm đang dùng, lần dùng cuối) thì nó chỉ là mỹ từ. RTB ở mục 5 là bắt buộc, không phải nice-to-have.
- **USP #1 phụ thuộc vào chất lượng scanner.** Nếu quét ra kết quả nhiễu, toàn bộ định vị "bắt đầu từ hỗn loạn" sụp. Đây là hạng mục kỹ thuật rủi ro nhất và cần làm trước.
