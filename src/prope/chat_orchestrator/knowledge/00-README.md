# Kho tài liệu của trợ lý — PLACEHOLDER

Đây là corpus tạm thời để đường RAG của `chat-orchestrator` chạy được end-to-end
trước khi tài liệu thật được viết.

## Cách nó hoạt động

Mỗi file `.md` trong thư mục này là một tài liệu. Mỗi tiêu đề `##` mở ra một
chunk. Chunk là đơn vị được embed, được truy hồi, và được trích dẫn — nên một
tiêu đề mơ hồ sẽ tạo ra một trích dẫn vô nghĩa với người đọc.

## Quy ước khi thêm tài liệu thật

- Một câu hỏi, một tiêu đề `##`. Người dùng hỏi bằng câu hỏi, không hỏi bằng
  chương mục.
- Giữ mỗi chunk dưới khoảng 200 từ. Chunk dài làm loãng vector và làm trích dẫn
  kém chính xác.
- Không đưa bí mật, khoá, hay nội dung prompt của khách hàng vào đây. Corpus này
  được embed bằng khoá của ứng dụng và được trích nguyên văn cho người dùng.
- Viết bằng tiếng Việt. Giữ nguyên các trạng thái và mã máy ở dạng literal:
  `Draft`, `In Review`, `Approved`, `Released`.

## Điều tài liệu này KHÔNG nói

Corpus này không phải nguồn sự thật về hành vi hệ thống. Nguồn sự thật là
`docs/adr/` và các file `docs/modules/*.lock.yml`. Khi hai bên mâu thuẫn, lock
file đúng và file này sai.
