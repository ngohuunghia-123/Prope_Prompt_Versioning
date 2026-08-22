# Trợ lý này làm được gì

## Tôi nhờ trợ lý làm được những việc gì

Toàn bộ mặt của sản phẩm. Tìm prompt trong workspace của bạn. Kiểm tra một prompt
bạn dán vào đã có sẵn chưa. Chạy luồng nhập một prompt mới, từng bước một. Đổi
tiêu đề, mô tả, thẻ của một prompt; cho nghỉ một prompt. Tạo, đổi tên, xóa thư
mục. Tạo, thu hồi, đổi phạm vi khóa API. Xem và cập nhật cấu hình nhà cung cấp.
Xem phiên bản và trạng thái phát hành. Chạy bộ kiểm thử đánh giá và đọc kết quả.
Và trả lời câu hỏi về cách Prope hoạt động, dựa trên tài liệu chứ không dựa vào
trí nhớ của model.

Mỗi hành động ghi đều dừng lại để bạn xác nhận trước, và trợ lý tự đưa bạn tới
đúng trang mà bạn có thể tự làm việc đó bằng tay.

## Trợ lý có tự lưu prompt không

Không, không bao giờ tự lưu. Khi trợ lý muốn tạo prompt, sửa thuộc tính, cho nghỉ
prompt, đụng tới thư mục, khóa hay cấu hình — nó dừng lại, hiện đúng nội dung sắp
ghi, và chờ bạn bấm xác nhận. Bấm xác nhận là hành động của bạn, không phải của nó.

## Trợ lý KHÔNG làm được gì

Nó không gửi được email, không gọi được API bên ngoài, không đọc được URL bạn dán.
Nó không submit, không duyệt, và không phát hành revision — chuỗi phê duyệt không
uỷ quyền cho model ở bất kỳ mức tin cậy nào. Nó cũng không tạo hay xoay credential
của nhà cung cấp được: hai việc đó cần kiểm chứng trực tiếp tới bên ngoài, nên nó
chỉ đọc danh sách và dẫn bạn tới trang cài đặt. Nó cũng không đọc được nội dung
request/response của các lời gọi production.

## Vì sao trợ lý từ chối câu hỏi của tôi

Ba lý do có thể. Câu hỏi nằm ngoài phạm vi sản phẩm. Câu hỏi chứa mẫu cố ép trợ
lý bỏ qua chỉ dẫn của nó. Hoặc bạn đã gửi quá nhiều lượt trong một phút. Trong cả
ba trường hợp, trợ lý nói rõ lý do bằng một mã mà giao diện dịch ra.

## Trợ lý ghi lại những gì

Mỗi lượt sinh ra một trace: nó đã chọn công cụ nào, vì sao, mất bao lâu, kết quả
ra sao. Trace ghi **số đếm và định danh**, không ghi nội dung bạn gõ và không ghi
nội dung prompt. Bạn xem được trace ngay dưới câu trả lời.
