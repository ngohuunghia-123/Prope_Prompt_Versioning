# Quyền truy cập và riêng tư

## Mặc định của một prompt là gì

Riêng tư. Một prompt mới chỉ người sở hữu nhìn thấy, cho tới khi có người cấp
quyền hoặc đổi mức truy cập sang `workspace`. Khi người dùng không được nhìn thấy
một prompt, hệ thống trả về **không tìm thấy**, không phải **bị từ chối** — vì
"bị từ chối" là lời xác nhận rằng prompt đó tồn tại.

## Vì sao có lúc tôi thấy "không tìm thấy" cho prompt tôi biết là có

Vì bạn không có quyền đọc nó. Hai câu trả lời được thiết kế để không phân biệt
được: một prompt không tồn tại và một prompt bạn không được thấy trả về cùng một
hình dạng.

## Ba nhóm quyền tách rời

`prompt.edit`, `revision.submit`/`review`, và `release` là ba quyền khác nhau.
Việc tách chúng là ràng buộc không thương lượng của sản phẩm, không phải tuỳ chọn
cấu hình theo workspace.

## Khi một người rời tổ chức

Bản ghi `access.user` của họ được đánh dấu tombstone. Các dòng lịch sử không bao
giờ bị xoá, kể cả khi đó — `actor_id` sống tiếp như một giá trị không định danh
được, nên nhật ký phê duyệt vẫn nguyên vẹn.

## Trợ lý này thấy được gì

Trợ lý chỉ đọc được đúng những prompt mà **bạn** đọc được. Nó chạy sau cùng một
bộ lọc hiển thị như thanh tìm kiếm, nên nó không thể tiết lộ một prompt riêng tư
của người khác kể cả khi được yêu cầu trực tiếp.
