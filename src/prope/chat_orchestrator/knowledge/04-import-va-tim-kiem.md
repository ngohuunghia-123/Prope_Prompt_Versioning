# Nhập prompt và tìm kiếm

## Nhập một prompt gồm những bước nào

Năm bước: dán nguồn, chuyển sang XML chuẩn, kiểm tra trùng lặp, xem lại, rồi lưu.
Bốn bước đầu không ghi gì cả. Chỉ bước cuối tạo prompt và revision đầu tiên, và
nó cần một xác nhận rõ ràng của người dùng.

## Chuyển đổi XML làm gì

Nó nhận nguồn TXT, Markdown, JSON hoặc YAML và trả về các khối XML chuẩn của
Prope. Nó **không** lưu revision. Tác giả xem và sửa XML trước khi bấm lưu, và
bản gốc được giữ lại trên revision như dấu vết nguồn gốc.

## Kiểm tra trùng lặp trả lời câu gì

Nó xếp hạng các prompt bạn nhìn thấy được theo mức giống với văn bản bạn dán. Một
danh sách rỗng nghĩa là "không có gì giống thứ này trong những gì bạn thấy" — nó
không phải giấy chứng nhận rằng prompt này chưa từng tồn tại.

## Có hai kiểu tìm kiếm

**Quick search** so khớp theo từ, không gọi model, không tốn chi phí nhà cung
cấp. **AI search** nhúng câu hỏi thành vector và xếp hạng theo ngữ nghĩa, nên nó
tìm được prompt diễn đạt khác hẳn với từ bạn gõ. Quick là mặc định vì nó nhanh và
không phụ thuộc nhà cung cấp.

## Vì sao một prompt chưa index vẫn tìm được

Vì đường tìm kiếm theo từ đọc tài liệu do trigger của cơ sở dữ liệu duy trì, luôn
có sẵn. Index vector làm cho việc tìm nhanh hơn và hiểu ngữ nghĩa hơn — nó không
phải thứ quyết định một prompt có tìm được hay không.
