/**
 * ADR-0068's detector catalogue, in Vietnamese. The interface language (ADR-0053).
 *
 * **One key per `detector_id` and per `remedy_family`, and CI fails the build on
 * a missing one** — `tests/contract/test_improvement_codes_have_a_vi_key.py`
 * reads both closed catalogues out of Python and this file out of TypeScript. A
 * code with no key renders as a blank row, and a blank row in a queue somebody is
 * meant to act on is worse than no queue: it is a signal nobody can read.
 *
 * **The server sends a `code` and numbers; this file has the sentences.** Every
 * `{{param}}` below is interpolated from a finding's `params`. There is no
 * `message` field on the wire and there must not be one.
 *
 * The one exception is a finding's `evidence_line`, which the server generates
 * directly in Vietnamese — no English intermediate, because a translation step
 * would be a second model call on the display path — and which has already passed
 * its redaction rail before storage.
 *
 * **The empty state is not an apology.** An empty inbox is the success condition
 * (A-162's inversion), and the copy says so.
 */
export const improvementVi = {
  inbox: {
    title: 'Theo dõi sau phát hành',
    subtitle: 'Prompt đã phát hành có còn làm đúng việc đã được duyệt không?',
    empty: 'Không có phát hiện nào. Lần quét gần nhất thấy mọi prompt đã phát hành đều bình thường.',
    emptyHint: 'Đây là trạng thái tốt, không phải thiếu dữ liệu.',
    warnings: '{{count}} cảnh báo',
    advice: '{{count}} góp ý',
    occurrences: 'Đã xảy ra {{count}} lần',
    firstSeen: 'Lần đầu: {{when}}',
    lastSeen: 'Gần nhất: {{when}}',
    openPrompt: 'Mở prompt',
    tabEmpty: 'Prompt này chưa có phát hiện nào.',
    tabEmptyHint: 'Lần quét gần nhất đã xem prompt này và thấy bình thường.',
    dismiss: 'Bỏ qua',
    dismissReason: 'Lý do bỏ qua',
    dismissReasonPlaceholder: 'Vì sao mục này không đáng xử lý?',
    dismissReasonRequired: 'Cần nêu lý do — tỉ lệ bỏ qua là căn cứ để rút một bộ dò khỏi danh sách.',
  },
  severity: {
    warning: 'Cảnh báo',
    advice: 'Góp ý',
  },
  proposal: {
    expiresAt: 'Hết hạn {{when}}',
    accept: 'Mở trình soạn thảo với nội dung đề xuất',
    acceptHint: 'Chưa có gì thay đổi. Bản sửa chỉ được ghi khi bạn tự lưu một phiên bản mới.',
    dismiss: 'Không áp dụng',
    gateTitle: 'Kết quả chạy bộ case của chính prompt này',
    gateSummary: '{{candidate}}/{{total}} case đạt, trước đó {{baseline}}/{{total}}',
    gateHint:
      'Đề xuất chỉ hiện ra sau khi đã chạy qua bộ case và không làm hỏng case nào đang đạt.',
    gateLimit: 'Bộ case chỉ mạnh bằng những gì nó đo. Đây là mức sàn, không phải bằng chứng đầy đủ.',
    caseBaseline: 'Trước',
    caseCandidate: 'Sau',
    noBody: 'Đề xuất này không kèm nội dung sửa.',
    prefillTitle: 'Nội dung đề xuất đã được điền vào biểu mẫu',
    prefillBody:
      'Đây là nội dung do đề xuất sinh ra, chưa được lưu. Hãy đọc lại, sửa nếu cần, rồi lưu một phiên bản mới — prompt đang phát hành vẫn giữ nguyên cho tới lúc đó.',
  },
  kind: {
    note: 'Thông tin',
    case: 'Đề xuất bổ sung case',
    edit: 'Đề xuất sửa nội dung',
  },
  family: {
    tighten_refusal_block: {
      title: 'Siết lối từ chối',
      body: 'Thêm một khối ràng buộc nói rõ khi nào phải từ chối và không được tiết lộ hướng dẫn hệ thống.',
    },
    add_length_rule: {
      title: 'Thêm giới hạn độ dài',
      body: 'Thêm một khối định dạng đầu ra nêu rõ độ dài tối đa, thay vì để câu trả lời bị cắt ngang.',
    },
    add_brevity_clause: {
      title: 'Thêm yêu cầu ngắn gọn',
      body: 'Thêm ràng buộc trả lời ngắn gọn, để giảm phần token đầu ra đang tăng.',
    },
  },
  schedule: {
    title: 'Đo lại hàng rào bảo vệ theo lịch',
    description:
      'Chạy lại bộ case đối kháng lên bản đang phát hành, để phát hiện hàng rào bị vô hiệu khi nhà cung cấp thay đổi mô hình.',
    enabled: 'Bật',
    cadence: 'Chu kỳ (ngày)',
    cost: 'Mỗi chu kỳ tiêu credit nhà cung cấp của workspace, và lặp lại cho tới khi bạn tắt.',
    costHint:
      'Prope không hiển thị số tiền ước tính vì chưa đo được. Trần chi tiêu là thứ chặn thật sự — phép đo bị từ chối khi chạm trần.',
    scopeAll: 'Áp dụng cho mọi prompt đã phát hành',
    scopeSome: 'Đang chọn {{namespaces}} nhóm và {{prompts}} prompt',
    lastRun: 'Chạy gần nhất: {{when}}',
    never: 'Chưa chạy lần nào',
    save: 'Lưu lịch',
    saving: 'Đang lưu…',
    saved: 'Đã lưu lịch.',
    failed: 'Không lưu được lịch. Có thể bạn không có quyền quản lý chi tiêu.',
  },
  detector: {
    truncation_rising: {
      title: 'Câu trả lời bị cắt ngang nhiều hơn',
      body: '{{share}} lượt gọi bị cắt ngang, trước đó là {{prior_share}}. Phần token bị cắt vẫn bị tính tiền.',
      action: 'Nêu rõ độ dài tối đa trong prompt, hoặc nâng max_tokens ở phía gọi',
    },
    fallback_rising: {
      title: 'Người dùng đang nhận câu trả lời dự phòng',
      body: '{{share}} lượt gọi rơi vào câu trả lời dự phòng, trước đó là {{prior_share}}. Bản đã phát hành đang lỗi ở phía nhà cung cấp.',
      action: 'Kiểm tra cấu hình nhà cung cấp và bản đang phát hành',
    },
    caller_error_clustering: {
      title: 'Phía gọi đang gửi sai',
      body: '{{share}} lượt gọi bị từ chối vì lỗi phía gọi, trước đó là {{prior_share}}. Thường là thiếu biến hoặc sai cấu trúc messages.',
      action: 'Đối chiếu phần tích hợp với danh sách biến của bản đang phát hành',
    },
    output_ratio_drift: {
      title: 'Model đang trả lời dài hơn',
      body: 'Tỉ lệ token ra trên token vào là {{ratio}}, trước đó là {{prior_ratio}}. Token đầu ra đắt hơn nhiều lần token đầu vào.',
      action: 'Thêm yêu cầu trả lời ngắn gọn',
    },
    usage_unknown_appearing: {
      title: 'Nhà cung cấp ngừng báo mức sử dụng',
      body: '{{count}} lượt gọi không có số liệu token. Mọi con số chi phí sau thời điểm này là THIẾU, không phải bằng không.',
      action: 'Kiểm tra phiên bản API của nhà cung cấp',
    },
    cost_unpriced_appearing: {
      title: 'Có mô hình chưa có bảng giá',
      body: '{{count}} lượt gọi chạy trên một mô hình chưa có dòng giá tương ứng.',
      action: 'Thêm dòng giá cho mô hình đang phục vụ',
    },
    latency_tail_shift: {
      title: 'Độ trễ đuôi tăng',
      body: 'P95 là {{p95_ms}}ms, trước đó là {{prior_p95_ms}}ms. Phần đuôi mới là trải nghiệm thật của người dùng.',
      action: 'Xem lại mô hình và tham số của bản đang phát hành',
    },
    pinned_share_rising: {
      title: 'Bên tiêu thụ đang ghim khỏi bản phát hành',
      body: '{{share}} lượt gọi ghim vào một phiên bản cụ thể thay vì bản đã phát hành, trước đó là {{prior_share}}.',
      action: 'Hỏi bên tích hợp vì sao họ không dùng bản đã duyệt',
    },
    chain_depth_rising: {
      title: 'Có dấu hiệu gọi lặp ở phía tích hợp',
      body: '{{share}} lượt gọi nằm trong một chuỗi, trước đó là {{prior_share}}. Thường là vòng lặp hoặc thử lại ở phía agent.',
      action: 'Xem lại logic thử lại ở phía gọi',
    },
    released_but_unused: {
      title: 'Prompt đã phát hành nhưng không ai gọi',
      body: 'Đã phát hành {{days_since_release}} ngày và không có lượt gọi nào trong kỳ đo.',
      action: 'Cân nhắc thu hồi để giảm số prompt phải rà soát',
    },
    profile_drift: {
      title: 'Mục đích khai báo đã đổi sau khi phát hành',
      body: 'Hồ sơ sử dụng hiện tại khác với bản được đóng dấu lúc duyệt. Bản đang phục vụ được duyệt dưới một mức phơi nhiễm khác.',
      action: 'Tạo phiên bản mới để được duyệt lại dưới mục đích hiện tại',
    },
    probe_leak_appeared: {
      title: 'Hàng rào bảo vệ đã bị vô hiệu',
      body: '{{leaked}} trên {{cases}} case bị lọt, lần đo trước là {{prior_leaked}}. Không có lỗi nào được báo — đây là thứ chỉ đo lại mới thấy.',
      action: 'Siết lối từ chối trong prompt',
    },
  },
} as const;
