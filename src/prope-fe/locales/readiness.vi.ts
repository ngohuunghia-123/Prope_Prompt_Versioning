/**
 * ADR-0067's rule catalogue, in Vietnamese. The interface language (ADR-0053).
 *
 * **One key per `rule_id`, and CI fails the build on a missing one.**
 * `GET /api/v1/readiness/rules` exists so that assertion is possible at all:
 * `tests/contract/test_readiness_rules_have_a_vi_key.py` reads the closed
 * catalogue out of Python and this file out of TypeScript, and refuses a rule
 * with no title. A rule with no key renders as a blank row, and a blank row on a
 * readiness card is worse than no card — it is a warning nobody can act on.
 *
 * **The server sends a `code` and numbers; this file has the sentences.** Every
 * `{{param}}` below is interpolated from a finding's `params`. There is no
 * `message` field on the wire and there must not be one.
 *
 * The one exception is a finding's `evidence` line, which the server generates
 * directly in Vietnamese — no English intermediate, because a translation step
 * would be a second model call on the display path — and which has already
 * passed its redaction rail before storage.
 */
export const readinessVi = {
  card: {
    title: 'Mức độ sẵn sàng',
    empty: 'Không có phát hiện nào. Prompt này đã sẵn sàng cho mục đích đã khai báo.',
    warnings: '{{count}} cảnh báo',
    advice: '{{count}} góp ý',
    dismissed: '{{count}} đã bỏ qua',
    frozen: 'Bản đã đóng băng cho người duyệt',
    frozenHint:
      'Đây là bản ghi tại thời điểm gửi duyệt. Nó không thay đổi khi bộ quy tắc được cập nhật.',
    live: 'Đang cập nhật theo bản nháp',
    catalogueVersion: 'Bộ quy tắc v{{version}}',
    laneBUnavailable: 'Không chạy được phần phân tích bằng mô hình. Các mục còn lại vẫn đầy đủ.',
    showDismissed: 'Hiện các mục đã bỏ qua',
    hideDismissed: 'Ẩn các mục đã bỏ qua',
    dismiss: 'Bỏ qua',
    dismissReason: 'Lý do bỏ qua',
    dismissReasonPlaceholder: 'Vì sao mục này không áp dụng cho prompt này?',
    dismissReasonRequired: 'Cần nêu lý do — tỉ lệ bỏ qua là căn cứ để rút một quy tắc khỏi bộ.',
    dismissedBecause: 'Đã bỏ qua: {{reason}}',
    viewProposedEdit: 'Xem chỉnh sửa đề xuất',
    evidenceLabel: 'Dẫn chứng',
  },

  /**
   * Which lane produced a finding. Rendered as a badge, because the difference
   * between a MEASUREMENT and an opinion is the thing a reader most needs before
   * deciding how much weight to give a row.
   */
  lane: {
    static: 'Kiểm tra tĩnh',
    probe: 'Đo thực tế',
    drafted: 'Mô hình đề xuất',
  },

  severity: {
    warning: 'Cảnh báo',
    advice: 'Góp ý',
  },

  /** The profile clause that admitted a finding, rendered as *why am I seeing this*. */
  admitted: {
    always: 'Áp dụng cho mọi prompt',
    untrusted_input_present: 'Vì prompt này nhận nội dung không tin cậy',
    all_three_legs: 'Vì prompt này hội đủ cả ba yếu tố rủi ro',
    can_act_or_absorbs_untrusted: 'Vì prompt này có thể hành động hoặc nhận nội dung ngoài',
  },

  profile: {
    title: 'Prompt này dùng để làm gì?',
    description:
      'Bốn khai báo dưới đây quyết định những gì bạn được cảnh báo. Prompt nội bộ sẽ không bị nhắc về rào chắn dành cho người dùng công khai.',
    undeclaredBadge: 'Chưa khai báo — đang giả định trường hợp xấu nhất',
    undeclaredHint:
      'Chưa ai khai báo mục đích sử dụng, nên mọi quy tắc đang chạy ở mức nghiêm ngặt nhất. Chọn đúng một lần là xong.',
    assumedAs: 'Đang giả định: {{value}}',
    axis: {
      audience: 'Ai gọi được prompt này?',
      untrusted_input: 'Nội dung không tin cậy nào đi vào ngữ cảnh?',
      acts: 'Đầu ra có thể gây ra điều gì?',
      sensitivity: 'Dữ liệu thuộc loại nào?',
    },
    value: {
      undeclared: 'Chưa khai báo',
      internal: 'Chỉ nội bộ',
      authenticated_user: 'Người dùng đã đăng nhập',
      public: 'Công khai',
      none: 'Không có',
      user_text: 'Văn bản người dùng nhập',
      retrieved: 'Nội dung truy xuất (RAG)',
      third_party: 'Nguồn bên thứ ba',
      answers_only: 'Chỉ trả lời',
      emits_tool_calls: 'Gọi công cụ',
      irreversible: 'Hành động không thể hoàn tác',
      synthetic: 'Dữ liệu giả lập',
      business: 'Dữ liệu nghiệp vụ',
      personal_data: 'Dữ liệu cá nhân',
    },
  },

  probe: {
    title: 'Đo bằng bộ case đối kháng',
    description:
      'Chạy bộ case tấn công đã đóng gói sẵn lên chính bản sửa đổi này. Kết quả là con số, không phải nhận định.',
    start: 'Chạy phép đo',
    running: 'Đang chạy…',
    cost: 'Dùng credit nhà cung cấp của workspace.',
    willRun: 'Sẽ chạy: {{sets}}',
    lastRun: 'Lần đo gần nhất',
    result: 'Từ chối {{refused}} trên {{total}} case',
    noSets: 'Với khai báo hiện tại, không có bộ case nào cần chạy.',
    refused: 'Đã từ chối',
    leaked: 'Bị vượt qua',
    errors: 'Lỗi gọi',
    errorsHint: 'Lỗi gọi không phải là điểm cộng — những case đó chưa được đo.',
    status: {
      running: 'Đang chạy',
      completed: 'Hoàn tất',
      partial: 'Hoàn tất một phần',
      failed: 'Thất bại',
    },
    refusal: {
      spend_ceiling_reached: 'Workspace đã chạm trần chi tiêu tháng này.',
      no_applicable_sets: 'Khai báo hiện tại không cần bộ case nào.',
      revision_has_no_binding: 'Bản sửa đổi này chưa gắn model để gọi.',
    },
  },

  /**
   * **One entry per `RuleId`.** The order matches `domain.py`, grouped by lane,
   * so a rule added there and forgotten here is visible as a gap in the sequence
   * as well as by the CI check.
   */
  rule: {
    interpolation_inside_instructions: {
      title: 'Biến được chèn vào trong khối hướng dẫn',
      body: '{{count}} biến ({{variables}}) nằm trong khối hướng dẫn. Nội dung thay vào đó sẽ được đọc như mệnh lệnh chứ không phải dữ liệu.',
      action: 'Chuyển biến sang khối ngữ cảnh',
    },
    placeholder_will_not_substitute: {
      title: 'Có chỗ trông như biến nhưng sẽ không được thay',
      body: 'Tìm thấy {{count}} chỗ ({{found}}) sẽ được gửi nguyên văn tới model, kể cả dấu ngoặc.',
      action: 'Sửa thành cú pháp {{"{{ten_bien}}"}}',
    },
    canonical_structure_weak: {
      title: 'Cấu trúc khối chưa chuẩn',
      body: 'Thứ tự khối hiện tại: {{order}}. Ngữ cảnh nên đứng trước hướng dẫn đọc nó.',
      action: 'Sắp xếp lại các khối',
    },
    no_eval_coverage: {
      title: 'Prompt chưa có bộ eval nào',
      body: 'Khi gửi duyệt, mọi bộ eval sẽ được chạy — và một prompt không có bộ nào thì luôn đạt.',
      action: 'Tạo bộ eval đầu tiên',
    },
    thin_eval_coverage: {
      title: 'Bộ eval còn mỏng',
      body: 'Hiện có {{cases}} case, dưới mức {{threshold}}. Đạt một bộ mỏng nói được rất ít.',
      action: 'Bổ sung case',
    },
    lethal_trifecta: {
      title: 'Hội đủ ba yếu tố rủi ro',
      body: 'Prompt này khai báo dữ liệu {{sensitivity}}, nhận nội dung {{untrusted_input}}, và có thể {{acts}}. Ba yếu tố cùng lúc là điều kiện đủ để một lệnh tiêm vào trở thành hành động thật.',
      action: 'Xem lại khai báo hoặc bỏ bớt một yếu tố',
    },
    body_cost: {
      title: 'Chi phí của riêng phần thân prompt',
      body: 'Khoảng {{approx_tokens}} token cho mỗi lượt gọi, trước cả đầu vào và đầu ra.',
      action: 'Rút gọn phần lặp',
    },
    profile_undeclared: {
      title: 'Chưa khai báo mục đích sử dụng',
      body: 'Còn thiếu {{missing}}. Mọi quy tắc phía trên đang chạy ở mức nghiêm ngặt nhất.',
      action: 'Khai báo mục đích sử dụng',
    },
    probe_injection_leaked: {
      title: 'Có case tiêm prompt không bị từ chối',
      body: '{{leaked}} trên {{total}} case tiêm prompt đã được model làm theo.',
      action: 'Thêm case này vào bộ eval',
    },
    probe_system_prompt_leaked: {
      title: 'Prompt hệ thống bị lộ ra ngoài',
      body: '{{leaked}} trên {{total}} case khiến model in lại một phần prompt hệ thống.',
      action: 'Thêm case này vào bộ eval',
    },
    probe_incomplete: {
      title: 'Phép đo chưa hoàn tất',
      body: '{{errors}} case lỗi khi gọi nhà cung cấp. Những case đó chưa được đo.',
      action: 'Chạy lại phép đo',
    },
    contradictory_instructions: {
      title: 'Hai hướng dẫn mâu thuẫn nhau',
      body: 'Có hai hướng dẫn không thể cùng làm theo.',
      action: 'Xem lại phần hướng dẫn',
    },
    redundant_body: {
      title: 'Nội dung lặp lại',
      body: 'Một hướng dẫn được nhắc lại nhiều lần. Phần lặp tốn token ở mọi lượt gọi.',
      action: 'Rút gọn phần lặp',
    },
    no_refusal_path: {
      title: 'Chưa có lối từ chối',
      body: 'Prompt nói phải làm gì nhưng không nói làm gì khi không thể. Khi đó model có xu hướng bịa.',
      action: 'Thêm hướng dẫn cho trường hợp không xử lý được',
    },
  },
} as const;
