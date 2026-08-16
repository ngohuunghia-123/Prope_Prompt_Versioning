# Gateway tương thích OpenAI

## Sản phẩm gọi prompt như thế nào

Trỏ một client tương thích OpenAI vào gateway của Prope và gọi prompt bằng **tên
model**. Sản phẩm tiêu thụ không bao giờ giữ bản sao của nội dung prompt — gateway
phân giải tên model thành bản revision đang được phát hành và phục vụ nó.

## Nếu tôi đổi bản phát hành thì sao

Lần gọi kế tiếp lấy bản mới, không cần deploy lại. Có một cache phân giải ngắn
(khoảng 30 giây) và cache đó **hết hạn** — không có cơ chế nào chủ động vô hiệu
hoá nó, nên thay đổi có hiệu lực trong vòng vài chục giây chứ không tức thì.

## Mỗi lời gọi được ghi lại những gì

Metadata: prompt nào, revision nào, model nào, bao nhiêu token, hết bao nhiêu
tiền, mất bao lâu. Đó là thứ làm cho câu "lời gọi này do bản nào phục vụ" trả lời
được. Nội dung request và response được lưu ở một kho riêng và **không có đường
đọc** trong bản MVP.

## Khoá API của workspace

Khoá do workspace cung cấp, được mã hoá khi lưu, không API đọc nào trả về, và bị
che ở mọi nơi hiển thị. Nếu bạn cần đổi khoá, bạn nhập khoá mới — không có cách
nào đọc lại khoá cũ.

## Khi tên model không phân giải được

Câu trả lời cho một tên model không tồn tại và câu trả lời cho một khoá không đủ
phạm vi là **giống hệt nhau tới từng byte**. Đó là chủ ý: một lỗi phân biệt được
sẽ biến gateway thành công cụ dò tên prompt của workspace khác.
