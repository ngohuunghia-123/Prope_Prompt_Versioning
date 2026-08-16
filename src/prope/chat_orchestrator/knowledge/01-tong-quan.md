# Prope là gì

## Prope giải quyết vấn đề gì

Prope là sổ đăng ký prompt và hệ thống kiểm soát phát hành, dành cho đội sản
phẩm mà prompt đang nằm rải rác trong lịch sử chat, Google Sheets, Notion và mã
nguồn. Mỗi prompt có một người sở hữu, một chuỗi phiên bản không thể sửa, một bộ
eval cố định, và một phê duyệt của con người được ghi lại trước khi bất cứ thứ gì
ra production.

## Ai dùng Prope

Ba vai. **Prompt Owner** — người viết và sửa prompt, không cần viết một dòng
code. **Reviewer/Approver** — người nhìn diff, kết quả eval và chênh lệch chi phí
trên cùng một màn hình rồi ghi lại quyết định. **Developer** — người trỏ một
client tương thích OpenAI vào gateway của Prope và gọi prompt theo tên model.

## Giá trị cốt lõi

Không prompt nào ra production mà không có phê duyệt của con người được ghi lại,
và mọi lời gọi đều truy ngược được về đúng bản revision đã phục vụ nó. Đây là thứ
một bảng tính không làm được.

## Prope không làm gì

Prope không huấn luyện model, không phục vụ model, và không giữ bản sao credential
của nhà cung cấp dưới dạng đọc được. Credential do workspace cung cấp, được mã
hoá khi lưu, và không API đọc nào trả chúng về.
