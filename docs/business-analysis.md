# Phân tích nghiệp vụ — Prope

> Phiên bản: 0.1 · 2026-08-06  
> Phạm vi: phân tích nghiệp vụ và yêu cầu cho Prope; không phải đặc tả kỹ thuật hoặc kế hoạch triển khai mã nguồn.

## 1. Cách đọc tài liệu

Mỗi mệnh đề được gắn một loại bằng chứng để tránh biến ý tưởng thành “sự thật”.

| Ký hiệu | Ý nghĩa |
|---|---|
| **[Xác nhận]** | Có trong tệp của repository; đường dẫn nguồn được ghi ngay tại mệnh đề. |
| **[Suy luận]** | Kết luận hợp lý rút ra từ bằng chứng, chưa phải điều đã được đo hoặc phê duyệt. |
| **[Giả định]** | Điều cần tạm coi là đúng để thiết kế/ước lượng; phải xác nhận trước khi cam kết. |
| **[Thiếu]** | Thông tin chưa tìm thấy trong repository. |

### Nguồn bằng chứng chính

- Nguồn chân lý sản phẩm: [`docs/prope_source_of_truth.md`](prope_source_of_truth.md), tự nhận là ngữ cảnh chuẩn cho chiến lược, UX, nghiên cứu, đặc tả, thiết kế và triển khai (mục 1–2).
- Bối cảnh bài toán và ràng buộc ban đầu: [`docs/research/runs/prompt-asset-register-solution-4fbe59/query.md`](research/runs/prompt-asset-register-solution-4fbe59/query.md).
- Định vị cạnh tranh: [`docs/product/positioning.md`](product/positioning.md).
- Tổng hợp nghiên cứu và các phản biện: [`docs/research/RESEARCH.vi.md`](research/RESEARCH.vi.md), đặc biệt các mục 2–11.
- Hiện trạng phần mềm: [`src/`](../src), [`tests/`](../tests), [`README.md`](../README.md), [`ARCHITECTURE.md`](../ARCHITECTURE.md).

## 2. Tóm tắt điều hành

**[Xác nhận]** Prope được định nghĩa là nền tảng doanh nghiệp quản lý prompt như “tài sản vận hành có chủ sở hữu”; giá trị cốt lõi là biến prompt phân tán thành tài sản có chủ sở hữu, lịch sử revision, quyền truy cập và đường đi đáng tin cậy tới production. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §2–3.

**[Xác nhận]** Bằng chứng khảo sát trong repo là định hướng, không đại diện thống kê: enterprise n=11 và individual hợp lệ n=15; chính nguồn chân lý cũng nêu hạn chế tuyển mẫu và yêu cầu kiểm chứng thêm. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §5, §21.

**[Suy luận]** Rủi ro lớn nhất không phải thiếu một “prompt library”, mà là xây một registry lớn nhưng không đáng tin: nhập liệu ban đầu phải ít ma sát, còn dữ liệu quan trọng phải có chủ sở hữu và được cập nhật bởi các hành động vận hành tự nhiên. Lý do: nghiên cứu nội bộ đã chỉ ra nguy cơ “registry decay” và xung đột giữa nhập hàng loạt không tốn công với việc giữ metadata có nghĩa. [`docs/research/RESEARCH.vi.md`](research/RESEARCH.vi.md) §2–3, §10; [`docs/research/runs/prompt-asset-register-solution-4fbe59/comparisons.md`](research/runs/prompt-asset-register-solution-4fbe59/comparisons.md) “Tension 2”.

**Khuyến nghị đóng khung:** xây một *Prompt Asset Register* theo từng bước, lấy luồng “đưa prompt vào → nhận diện chủ sở hữu → sửa thành revision → thu thập bằng chứng → phê duyệt → phát hành/khôi phục” làm hạt nhân. Chỉ chặn phát hành production, không biến mọi thao tác tác giả thành thủ tục duyệt. Đây là **[suy luận]** dựa trên nguyên tắc “capture before control”, HITL một cấp và MVP đã được nêu trong nguồn chân lý. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §11, §14–16.

## 3. Business problem framing

### 3.1 Tình huống, trigger và vấn đề gốc

| Nội dung | Phân loại | Bằng chứng / nhận định |
|---|---|---|
| Prompt đang nằm ở chat, ghi chú cá nhân, tệp cục bộ, Google Docs/Sheets, Notion, repository, email và tin nhắn nhóm. | **[Xác nhận]** | [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §3. |
| Các nhóm không rõ chủ sở hữu, revision mới nhất/đáng tin, hoặc prompt nào đang gây lỗi và cần khôi phục. | **[Xác nhận]** | [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §3, §5.1; [`docs/research/runs/prompt-asset-register-solution-4fbe59/query.md`](research/runs/prompt-asset-register-solution-4fbe59/query.md). |
| Vấn đề gốc là mất ownership, provenance và trust; không chỉ là thiếu nơi lưu prompt. | **[Xác nhận]** | [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §3. |
| Trigger nghiệp vụ là khi một prompt đã được nhiều người/hệ thống phụ thuộc hoặc cần đưa vào production. | **[Suy luận]** | Phù hợp câu chuyện vòng đời và nguyên tắc “mọi production prompt phải quy về owner, revision, approval record”. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §1, §11. |

### 3.2 Mục tiêu và tiêu chí thành công

| Mục tiêu | Chỉ số/điều kiện đã ghi nhận | Loại |
|---|---|---|
| Tìm revision đáng tin nhanh | ≥80% tác vụ tìm thành công trong <30 giây. | **[Xác nhận — giả thuyết cần kiểm chứng]** [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) H-01. |
| Bảo vệ release | ≥90% usage production trỏ tới revision approved; 100% release có version ID. | **[Xác nhận — mục tiêu/hypothesis]** [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) H-02, H-05. |
| Không biến kiểm soát thành nút thắt | Median review <1 ngày làm việc; ≥70% báo không bị chậm đáng kể. | **[Xác nhận — hypothesis]** [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) H-04. |
| Giảm khôi phục thủ công | Không copy-paste prompt thủ công trong pilot; restore <5 phút. | **[Xác nhận — hypothesis]** [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) H-05. |

### 3.3 Phạm vi

**Trong phạm vi MVP — [xác nhận]:** registry/search, owner, revision history/diff, trạng thái Draft/In review/Approved, private/team access, một reviewer, quyết định review có ghi nhận, và API/export đơn giản cho revision đã approved. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §16.

**Ngoài phạm vi MVP — [xác nhận]:** multi-level approval, semantic clustering nâng cao, analytics chi phí nâng cao, đầy đủ SDK/environment orchestration, policy engine phức tạp, full observability và workflow pháp lý về sở hữu trí tuệ. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §16.

**Ràng buộc không thương lượng — [xác nhận]:** HITL trước khi promote production, phân quyền sửa theo vai trò, regression eval, và cảnh báo tăng token/chi phí. [`docs/research/runs/prompt-asset-register-solution-4fbe59/query.md`](research/runs/prompt-asset-register-solution-4fbe59/query.md).

### 3.4 Lựa chọn định hướng

| Lựa chọn | Đánh giá |
|---|---|
| Xây lại toàn bộ observability/prompt runtime | Không khuyến nghị. **[Xác nhận]** Prope chủ ý không là nền tảng tracing/observability hay autonomous deployment. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §2, §11. |
| Chỉ làm thư viện prompt | Không đủ. **[Xác nhận]** định vị yêu cầu ownership, revision, access và trusted path to production. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §2–3. |
| Làm registry + lớp review/release, tích hợp runtime hiện hữu | Khuyến nghị. **[Suy luận]** Đây phù hợp định vị “layer, không phải replacement” và giảm phạm vi; tuy nhiên phải xác nhận các runtime/nhà cung cấp thật trong pilot. [`docs/product/positioning.md`](product/positioning.md) §4, §6. |

## 4. Stakeholder analysis

### 4.1 Stakeholder register và engagement

| Nhóm | Lợi ích/chính kiến | Power / interest | Cách tương tác đề xuất |
|---|---|---|---|
| Prompt Owner (designer, marketer, PM, domain expert) | Cần đưa prompt vào không cần code, tìm lại, giữ revision và kiểm soát access. **[Xác nhận]** [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §4.1. | Cao / cao | Prototype usability; kiểm thử luồng capture–find–reuse hằng tuần. **[Suy luận]** |
| Reviewer/Approver (manager, product/domain/compliance/technical approver) | Cần thấy owner, thay đổi, quality/cost/risk, nơi dùng; approve/reject và để lại quyết định. **[Xác nhận]** [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §4.2. | Cao / cao | Đồng thiết kế evidence card và SLA review; thử nghiệm decision time. **[Suy luận]** |
| Developer/AI Engineer | Cần lấy revision approved, pin version, release/restore an toàn, truy vết app về record. **[Xác nhận]** [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §4.3. | Cao / cao | Technical spike về API/export và runtime adapter trước khi hứa SDK. **[Suy luận]** |
| Security/compliance | Không được nêu như persona độc lập; product có rủi ro bảo mật và quyền truy cập. **[Thiếu]** | Cao / trung bình | Xác định data classification, retention, audit và quyền phê duyệt. **[Giả định]** |
| Sponsor/đơn vị vận hành tập đoàn | Cần adoption và lợi ích cross-team; chưa xác định buyer/champion đầu tiên. **[Thiếu]** [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §20. | Cao / cao | Chỉ định sponsor, pilot team và outcome owner trước pilot. **[Suy luận]** |

### 4.2 RACI tối thiểu đề xuất

| Hoạt động | Prompt Owner | Reviewer | Developer/AI Engineer | Sponsor | Security/compliance |
|---|---:|---:|---:|---:|---:|
| Đăng ký/import prompt | R/A | I | C | I | C |
| Sửa revision và nộp review | R | A (quality decision) | C | I | C |
| Định nghĩa/sửa eval contract | C | A | R | I | C |
| Promote production | R | A | R | I | C |
| Restore revision | C | A* | R | I | C |
| Chính sách RBAC/audit | I | C | C | A | R |

* **[Giả định]** Restore production cần review/ủy quyền tương đương promote; nguồn hiện tại không quy định rõ. Quy tắc này giảm rủi ro nhưng cần product owner xác nhận.

### 4.3 Xung đột cần quản trị

- **[Xác nhận]** Người dùng có thể ngại chia sẻ prompt cá nhân, lo security và integration; họ cũng sợ approval làm chậm công việc. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §5.1.
- **[Suy luận]** Thiết kế cần private-by-default, import không auto-share/auto-release, và một điểm kiểm soát duy nhất tại production; nếu không, adoption sẽ quay về Sheet/Notion.
- **[Thiếu]** Chưa có owner cho từng field của registry, ngưỡng escalation hoặc SLA review thực tế.

## 5. As-is process

### 5.1 Quy trình hiện tại được tái dựng

```text
Người tạo viết/sửa prompt ở code, Sheet, Notion, chat hoặc tệp cá nhân
  → tìm lại bằng chat/tin nhắn/email hoặc viết lại
  → có thể tồn tại nhiều prompt tương tự và không rõ bản tin cậy
  → ứng dụng/nhóm dùng một bản bằng copy-paste hoặc cách không được ghi nhận
  → khi output/cost có vấn đề, khó biết owner, revision đang chạy và cách khôi phục
```

Đây là **[xác nhận]** về các pain point và nơi lưu trữ, không phải workflow quan sát trực tiếp: nguồn chỉ có survey và mô tả vấn đề. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §3, §5; [`docs/research/runs/prompt-asset-register-solution-4fbe59/query.md`](research/runs/prompt-asset-register-solution-4fbe59/query.md).

### 5.2 Handoff, pain point và ngoại lệ

| Điểm | Xác nhận | Rủi ro/gap |
|---|---|---|
| Tạo/lưu → tìm lại | 4/11 enterprise tìm trong chat/message/email, 3/11 viết lại, 2/11 không có cách nhất quán. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §5.1. | Mất thời gian và nhân bản prompt. |
| Sửa → biết bản đúng | 11/11 enterprise không biết latest revision; 13/15 individual sửa mà không lưu revision cũ. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §5. | Không thể so sánh/khôi phục đáng tin. |
| Dùng → biết accountability | 9/11 enterprise không biết owner; 5/11 không nhận diện được prompt gây vấn đề. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §5.1. | Incident triage và stewardship không rõ. |
| Release → kiểm tra | 0/11 có formal approval. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §5.1. | Không có bằng chứng quyết định nhất quán. |

**[Thiếu]** Không có interview/observation log chứng minh cách từng team thực sự release prompt, ngoại lệ khẩn cấp, tool nào đang chạy production, hoặc thời gian xử lý hiện tại. Vì vậy không nên gọi workflow trên là “quy trình chính thức”.

## 6. Business rules register

| ID | Quy tắc nguyên tử | Loại | Nguồn / trạng thái |
|---|---|---|---|
| BR-01 | Prompt import phải ở trạng thái private mặc định; không được auto-publish hoặc auto-share. | **[Xác nhận]** | [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §6, §11, S4. |
| BR-02 | Mỗi prompt production phải quy về owner, revision và approval record. | **[Xác nhận]** | [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §11, §18. |
| BR-03 | Chỉ revision Approved mới được release/retrieve cho production. | **[Xác nhận]** | [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §10.5, S7; [`docs/research/runs/prompt-asset-register-solution-4fbe59/query.md`](research/runs/prompt-asset-register-solution-4fbe59/query.md). |
| BR-04 | Promote production phải có human-in-the-loop approval. | **[Xác nhận]** | [`docs/research/runs/prompt-asset-register-solution-4fbe59/query.md`](research/runs/prompt-asset-register-solution-4fbe59/query.md). |
| BR-05 | Quyết định review phải lưu evidence, comment/decision, reviewer và thời điểm. | **[Suy luận]** | Persona yêu cầu recorded decision và S6 yêu cầu decision history; các field chính xác chưa được chốt. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §4.2, S6. |
| BR-06 | Mọi thay đổi cần tạo revision bất biến, có editor và timestamp. | **[Xác nhận]** | S2 yêu cầu automatic snapshots, editor, timestamp, history/diff. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) S2. |
| BR-07 | Trước promote, hiển thị chênh lệch token/cost; cost phải đo end-to-end, không suy từ độ dài prompt. | **[Xác nhận + suy luận]** | Cảnh báo cost là hard constraint. [`docs/research/runs/prompt-asset-register-solution-4fbe59/query.md`](research/runs/prompt-asset-register-solution-4fbe59/query.md). Cách đo end-to-end là kết luận nghiên cứu. [`docs/research/RESEARCH.vi.md`](research/RESEARCH.vi.md) §7. |
| BR-08 | Eval chỉ được chặn release theo tiêu chí deterministic/checkable; đánh giá chất lượng chủ quan là evidence tư vấn và cần monitor drift định kỳ. | **[Suy luận mạnh]** | Nghiên cứu chỉ ra LLM judge phụ thuộc task và pre-release gate không thấy provider drift. [`docs/research/RESEARCH.vi.md`](research/RESEARCH.vi.md) §5; [`docs/research/runs/prompt-asset-register-solution-4fbe59/comparisons.md`](research/runs/prompt-asset-register-solution-4fbe59/comparisons.md) “Tension 4”. |
| BR-09 | “Property” là ẩn dụ sản phẩm, không phải xác lập quyền sở hữu trí tuệ/pháp lý. | **[Xác nhận]** | [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §1, §7, §18. |
| BR-10 | Quyền thay đổi prompt và quyền thay đổi eval contract/threshold không nhất thiết giống nhau. | **[Suy luận]** | Nghiên cứu khuyến nghị permission boundary quanh eval contract; chưa có policy được phê duyệt. [`docs/research/runs/prompt-asset-register-solution-4fbe59/comparisons.md`](research/runs/prompt-asset-register-solution-4fbe59/comparisons.md) “Convergences”. |

## 7. Domain model đề xuất

Đây là glossary **[đề xuất]**, chưa phải thuật ngữ đã được phê duyệt. Các tên ưu tiên bám theo language system của sản phẩm. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §8.

| Khái niệm | Định nghĩa làm việc | Quan hệ chính |
|---|---|---|
| Prompt property / Prompt | Đơn vị registry đại diện cho prompt có mục đích sử dụng. | Có một Prompt Owner; có nhiều Revision; có access policy. |
| Prompt Owner | Cá nhân/nhóm chịu trách nhiệm stewardship cho prompt. | Sở hữu Prompt; có thể nộp Revision. |
| Revision | Ảnh chụp bất biến của prompt tại một thời điểm. | Thuộc một Prompt; có status và evidence. |
| Eval contract | Tiêu chí, dữ liệu và threshold để kiểm tra revision theo task. | Đánh giá Revision; có owner/quyền thay đổi riêng. |
| Review decision | Bản ghi approve/request-changes cùng reviewer, evidence và thời gian. | Gắn với một Revision; tiền điều kiện của Release. |
| Release | Liên kết revision Approved với một environment/consumer. | Có version ID; có thể được Restore. |
| Usage observation | Telemetry/API event cho biết revision được consumer sử dụng. | Cập nhật last-used, usage/cost và blast radius. |

**[Thiếu]** Cần quyết định trước khi cố định mô hình: owner thuộc cá nhân hay team; nhiều steward có được không; approval gắn với revision hay release; transfer ownership; và schema tối thiểu khi import. Đây cũng là open-question register sẵn có. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §20.

## 8. To-be process

```text
1. Capture/import prompt (private, chưa governed)
2. Owner claim/assign + ghi mục đích và access
3. Tạo/sửa revision
4. Tạo hoặc chọn eval contract; chạy checks và cost comparison
5. Nộp review: evidence card = diff, deterministic checks, quality evidence,
   delta cost, usage/blast radius, recommendation
6. Reviewer approve hoặc request changes
7. Developer/owner release revision Approved tới environment
8. Runtime/API usage cập nhật usage, cost, last-used
9. Khi có incident: xác định release/revision → restore revision đã Approved
```

### Thay đổi so với hiện trạng

| Giữ lại | Thay đổi |
|---|---|
| Người không kỹ thuật vẫn có thể tạo/sửa prompt mà không cần code. **[Xác nhận]** [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §4.1. | Copy-paste không có record được thay bằng registry/revision có owner. **[Suy luận]** |
| Công cụ/runtimes hiện có vẫn có thể được dùng. **[Suy luận]** | Production nhận revision đã approved qua API/export/release, thay vì bản không xác minh. |
| Human judgement vẫn tồn tại. **[Xác nhận]** HITL bắt buộc. | Human judgement tập trung một lần tại promote, với evidence chuẩn hóa. **[Suy luận]** |

### Rủi ro chuyển đổi

- **[Xác nhận]** Import ồ ạt có thể tạo population prompt không được enrichment; research gọi đây là xung đột giữa zero-labor ingestion và registry đáng tin. [`docs/research/runs/prompt-asset-register-solution-4fbe59/comparisons.md`](research/runs/prompt-asset-register-solution-4fbe59/comparisons.md) “Tension 2”.
- **[Suy luận]** Gắn nhãn rõ `Imported/unclaimed` và chỉ coi prompt là governed sau claim/first-use/promotion; cần thử nghiệm lựa chọn trigger nào ít ma sát nhất.
- **[Xác nhận]** Review có thể thành rubber-stamp nếu card quá tải; giới hạn review vào evidence cần quyết định. [`docs/research/runs/prompt-asset-register-solution-4fbe59/comparisons.md`](research/runs/prompt-asset-register-solution-4fbe59/comparisons.md) “Tension 1”.

## 9. Requirements catalogue

### 9.1 Functional requirements

| ID | Requirement | Priority | Traceability / acceptance criterion |
|---|---|---:|---|
| FR-01 | Người dùng phải có thể thêm/import prompt, chọn owner và access; import mặc định private, không auto-share/release. | P0 | BR-01; S1/S3/S4. Nhập một prompt không tạo Release và chỉ owner thấy nó trước khi grant access. |
| FR-02 | Hệ thống phải lưu revision history bất biến, diff, editor và timestamp. | P0 | BR-06; S2. Một revision cũ vẫn đọc được sau khi tạo revision mới. |
| FR-03 | Registry phải hỗ trợ search/filter theo owner, status, access, trusted revision và related application nơi dữ liệu có. | P0 | S1. Người dùng hoàn thành find task trong mục tiêu đã nêu; metric còn cần baseline. |
| FR-04 | Hệ thống phải hỗ trợ Draft, In review, Approved, In use và Retired; không cho release revision chưa Approved. | P0 | BR-03; S3/S7. Request release revision Draft/In review bị từ chối với lý do rõ ràng. |
| FR-05 | Nộp review phải tạo evidence card gồm diff, evidence eval, delta token/cost, reviewer decision và thời gian. | P1 | BR-05/07; S5/S6. Thiếu evidence bắt buộc theo eval contract thì không submit được. |
| FR-06 | Reviewer phải approve hoặc request changes; quyết định có audit trail. | P1 | S6. Mỗi decision truy vết được revision, reviewer, thời gian và lý do. |
| FR-07 | API/export phải chỉ phân phối revision Approved, kèm version ID để consumer pin/trace. | P1 | BR-03; S7. Consumer không thể resolve revision unapproved qua production endpoint. |
| FR-08 | Hệ thống phải hiển thị và lưu cost/token delta trước promote; policy block/warn phải cấu hình được. | P1 | Hard constraint; S9. Case tăng cost vượt ngưỡng tạo cảnh báo trước quyết định. |
| FR-09 | Hệ thống phải hỗ trợ restore một revision Approved trước đó và ghi release history. | P1 | S2/S7. Restore tạo event audit, trỏ environment về revision đã chọn. |
| FR-10 | Tính năng similar prompt check chỉ là warning/triage, không được tự merge hoặc tự thay owner. | P2 | S8; nguyên tắc không auto-release/ownership explicit. |

### 9.2 Non-functional / control requirements

| ID | Requirement | Priority | Ghi chú |
|---|---|---:|---|
| NFR-01 | RBAC phải tách tối thiểu quyền edit prompt, review/approve, release và policy/eval-contract edit. | P0 | Ràng buộc RBAC có xác nhận; matrix chi tiết là **[thiếu]**. |
| NFR-02 | Mọi production release phải truy vết được owner, revision, decision/evidence và environment/usage context. | P0 | **[Xác nhận]** principle/agent rule. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §11, §18. |
| NFR-03 | Dữ liệu prompt phải private-by-default; retention, encryption, residency và PII policy phải được chốt trước pilot. | P0 | Private-by-default là **[xác nhận]**; các control cụ thể là **[thiếu]**. |
| NFR-04 | Eval không được tuyên bố “đảm bảo không giảm chất lượng” cho subjective task; UI/decision phải nêu loại evidence và giới hạn. | P0 | **[Suy luận mạnh]** từ research eval/drift. |
| NFR-05 | Production retrieval phải có chiến lược availability/fallback trước khi nằm trên request path. | P1 | **[Suy luận]**; chưa có SLO hoặc kiến trúc runtime được chốt. |

## 10. Requirements elicitation plan

| Mục tiêu cần xác minh | Kỹ thuật | Người tham gia | Output quyết định |
|---|---|---|---|
| Xác định workflow thật và nguồn prompt ưu tiên | Contextual interview + artifact walkthrough | 3 Prompt Owner, 2 Dev | Service blueprint, source priority, baseline time-to-find. |
| Kiểm tra capture/search có thay Sheet/Notion được | Prototype usability test | 5–8 người thuộc primary persona | Task success, time, failure reasons. |
| Chốt evidence card và gánh nặng review | Decision simulation với case thật | 3 Reviewer/Approver | Required evidence, SLA, escalation, card fields. |
| Chốt rule release/rollback và API scope | Technical workshop | Dev/AI engineer, SRE/security | Environment model, fallback, audit, integration spike. |
| Chốt quyền dữ liệu | Policy workshop | Sponsor, security/compliance, Owner | RBAC matrix, data classification, retention, ownership transfer. |
| Kiểm tra validity của eval | Eval-design workshop + offline replay | Domain owner, reviewer, AI engineer | Eval contract template; deterministic vs advisory checks; drift cadence. |

**[Xác nhận]** Chính product source of truth đề xuất 5–8 interview, prototype test cho Register & Trust/Review & Protect, một real-team pilot và brand comprehension test. [`docs/prope_source_of_truth.md`](prope_source_of_truth.md) §21.

## 11. Chất lượng yêu cầu và release readiness

### Đánh giá hiện tại: **Chưa sẵn sàng để cam kết triển khai production; sẵn sàng cho discovery prototype/P0 MVP có kiểm chứng.**

| Severity | Phát hiện | Sửa/decision cần có |
|---|---|---|
| Critical | “Regression eval để đảm bảo không giảm chất lượng” là tuyệt đối nhưng không khả thi cho subjective quality và không phát hiện model drift. | Thay bằng block deterministic contract + report subjective quality + scheduled drift monitoring; xác nhận policy với domain owner. |
| Critical | Không có mô hình quyền, data classification, retention hoặc policy xử lý nội dung nhạy cảm. | Chốt RBAC matrix và security baseline trước import prompt thật. |
| High | Chưa xác định buyer/champion, pilot team, nguồn import đầu tiên hoặc baseline KPI. | Chọn một team pilot và 3 task đo được; ghi baseline trước prototype. |
| High | Approval gắn với revision hay release, và rule emergency restore chưa được chốt. | Chốt state machine + exception/escalation policy. |
| Medium | Metric success là hypothesis, không phải commitment đã đo. | Gán owner, công thức đo, baseline và mốc thời gian cho từng KPI. |
| Medium | Sản phẩm/hệ thống hiện tại không triển khai domain logic Prope. | Tách discovery artifact khỏi claim implementation; chỉ công bố demo capability đã kiểm thử. |

### Kiểm tra traceability

- Vấn đề fragmentation/ownership/revision → FR-01 đến FR-04.
- Ràng buộc HITL/RBAC/eval/cost → FR-05 đến FR-08 và NFR-01 đến NFR-04.
- Khôi phục và consumption → FR-07, FR-09, NFR-02/NFR-05.
- Adoption → elicitation plan, pilot KPI và private-by-default.

## 12. Hiện trạng repository và khoảng cách thực thi

**[Xác nhận]** Repository chứa FastAPI app với `/health`, `/api/v1/chat`, `/api/v1/status`; route chat gọi LangGraph agent. [`src/main.py`](../src/main.py), [`src/api/routes.py`](../src/api/routes.py).

**[Xác nhận]** Agent graph chỉ có node `analyze` và `respond`; node hiện tạo chuỗi minh họa và đánh dấu TODO cho logic thực tế. [`src/agents/graph.py`](../src/agents/graph.py), [`src/agents/nodes/example_node.py`](../src/agents/nodes/example_node.py).

**[Xác nhận]** Công cụ knowledge search là placeholder và không có persistence/database/vector store đang được bật trong requirements; các dependency database/vector store đều được comment. [`src/agents/tools/example_tool.py`](../src/agents/tools/example_tool.py), [`requirements.txt`](../requirements.txt).

**[Suy luận]** Vì vậy không thể coi repo hiện tại đã cung cấp registry, versioning, RBAC, review, eval, cost control, SDK/release hay audit trail của Prope. Đây là khoảng cách delivery cần được quản trị rõ trong demo. Các tài liệu kiến trúc/đánh giá hiện cũng còn placeholder. [`ARCHITECTURE.md`](../ARCHITECTURE.md), [`eval/results/report.md`](../eval/results/report.md).

## 13. Open questions log

1. **[Thiếu]** Ai là sponsor/buyer và team pilot đầu tiên?
2. **[Thiếu]** Prompt source nào cần import đầu tiên, với quyền truy cập và dữ liệu nhạy cảm nào?
3. **[Thiếu]** Owner là một người hay team; steward, transfer và owner rời tổ chức xử lý ra sao?
4. **[Thiếu]** Approval gắn với revision, release, hay cả hai? Emergency restore có bypass không?
5. **[Thiếu]** Loại prompt/task nào có deterministic eval; ai sở hữu eval contract và threshold?
6. **[Thiếu]** Runtime/provider/environment thật và yêu cầu availability/fallback của consumer là gì?
7. **[Thiếu]** Cost dữ liệu lấy từ đâu, đơn vị chargeback/showback nào và ngưỡng cảnh báo/block nào?
8. **[Thiếu]** Quy định Vietnam/ngành cụ thể nào áp dụng cho dữ liệu, audit và human oversight? Không được suy diễn rằng EU AI Act tự động áp dụng.

## 14. Next decision sequence

1. Chọn pilot sponsor + một workflow production có thật.
2. Chốt RBAC, data boundary và state machine/release exception.
3. Prototype P0: capture, registry/search, owner, immutable revision, review decision.
4. Đo usability/baseline; chỉ sau đó thêm eval evidence và release integration.
5. Technical spike API/runtime telemetry/cost trước khi cam kết SDK hoặc cross-provider layer.

Tài liệu này hoàn thành theo thứ tự: problem framing → stakeholder analysis → as-is process → business rules → elicitation → domain model → to-be process → requirements pack → quality check. Không có application source code nào được sửa đổi.
