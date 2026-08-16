# Vòng đời của một prompt

## Một prompt đi qua những trạng thái nào

Một revision đi theo thứ tự: `Draft` → `In Review` → `Approved` → `Released`.
Người review có thể trả về `Changes Requested`, và revision quay lại `Draft`.
Trạng thái được lưu ở dạng literal ASCII và không được dịch khi lưu trữ; giao
diện dịch chúng khi hiển thị.

## Revision là bất biến

Sửa một prompt không ghi đè lên bản cũ. Nó tạo một revision mới với số thứ tự kế
tiếp trong cùng một transaction. Không có thao tác nào sửa nội dung một revision
đã tồn tại, và không có thao tác nào xoá nó. Đó là điều làm cho việc khôi phục
trở thành chuyện trỏ lại con trỏ chứ không phải chuyện triển khai lại.

## Ai được phát hành

Sửa, review/duyệt, và phát hành là ba quyền riêng biệt. Một người có thể giữ cả
ba, và khi họ tự duyệt prompt của chính mình thì việc đó được **ghi lại**, không
bị từ chối. Chỉ revision ở trạng thái `Approved` mới được phát hành hoặc được
gateway phân giải — điều này do một ràng buộc trong cơ sở dữ liệu bảo đảm, không
phải do mã ứng dụng.

## Break-glass là gì

Break-glass là đường phát hành khẩn cấp, được khai báo và được đếm. Nó không phải
quyền mà ai cũng có. Mỗi lần dùng sinh ra một công việc phải theo dõi trong vòng
24 giờ, và chính nghĩa vụ đó là thứ giữ cho nó hiếm.

## Rollback hoạt động thế nào

Con trỏ `released` của một prompt là một trường trong registry mà chỉ
release-control được ghi. Quay về một bản đã duyệt trước đó là ghi lại con trỏ đó
— không build lại, không deploy lại, và sản phẩm đang gọi không phải sửa gì.
