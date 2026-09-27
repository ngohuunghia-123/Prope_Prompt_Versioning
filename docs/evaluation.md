# Evaluation Evidence — Prope

> Bằng chứng hệ thống được đo lường, không chỉ "chạy được". Toàn bộ số liệu dưới đây
> nằm trong repo và tái tạo được bằng lệnh kèm theo.

## 1. Retrieval evaluation (prompt-search)

Nguồn: [`eval/README.md`](../eval/README.md), kết quả trong [`eval/result/`](../eval/result/) (14 file, chạy 2026-08-15).

**Thiết kế:** golden set 36 truy vấn viết tay + 6 duplicate probes, phân tầng độ khó (easy lookup, paraphrase không chung từ vựng, phân biệt cluster gần giống, tiếng Việt trên corpus tiếng Anh, adversarial out-of-scope mà đáp án đúng là danh sách rỗng). Relevance graded (`primary`/`secondary`), không nhị phân.

**Metric:** `hit_at_1`, `context_recall@3/@10`, `context_precision@3`, `mrr`, `ndcg@10`, `abstention_rate`, `latency p50/p95`.

**Chạy lại:**

```bash
PROPE_EVAL_DATABASE_URL="postgresql+asyncpg://postgres:eval@localhost:55432/prope" \
  python -m eval.retrieval.run_eval --limit 200 --label mychange
```

## 2. Versioning matrix — HITL lifecycle qua 5 kịch bản

Nguồn: [`eval/evidence/versioning-matrix/summary.md`](eval/evidence/versioning-matrix/summary.md) — trạng thái **EXECUTED / EVIDENCE_VALID**, có spec + screenshot cho từng scenario.

| Scenario | Kiểm chứng | Kết quả deterministic |
|---|---|---|
| S2 cost-guardrail | Cảnh báo chi phí khi candidate đắt hơn baseline | cả hai pass; `cost_warning=true` (ratio 7.84x) → human **không promote** |
| S3 instruction-regression | Candidate làm hỏng hành vi đã duyệt | pass → fail; BLOCK recommendation → reviewer request changes |
| S5 positive-improvement | Candidate cải thiện thật thì được release V2 | fail → pass → release |
| S6 contract-regression | Vi phạm output contract bị chặn trước người dùng | candidate refused `modality_mismatch`; BLOCK |
| S10 lifecycle-rollback | Release V2 rồi restore V1 qua gateway | header chuyển V2→V1 sau 35.9s; cả hai pass |

Điểm mấu chốt: mọi quyết định promote/block đều là **human decision có ghi nhận**, agent không tự promote.

## 3. Test suite như gate

**Quy mô lần chạy 26/08/2026: 3.552 test cases được collect** trên các nhóm unit, integration, security, architecture, contract, broker, evaluation, chaos, load, gateway và golden.

- `uv run pytest -q`: toàn bộ suite chạy trên PostgreSQL 17 + pgvector và RabbitMQ 4.3 **thật** qua testcontainers. Suite cố tình chỉ có **một** đường cấp phát — `tests/conftest.py` từ chối split service-container/local-compose ("two provisioning paths drift") — nên không có test nào chạy được mà không có engine thật.
- Suite kiến trúc assert các bất biến: RLS phủ mọi schema nghiệp vụ, append-only history ở mức DB privilege, route-table đầy đủ action vocabulary, không SQL cross-schema.
- `-m golden`: 10 similarity triplets có label; `make golden-live`: cùng bộ đó với LLM adjudicator thật (kết quả tại `eval/result/similarity-live.json`).

**Kết quả lần chạy gần nhất (26/08/2026, Windows, Python 3.13.15):**

| Lệnh | Kết quả |
|---|---|
| `uv run --with pytest-cov==7.0.0 pytest -q --cov=src/prope --cov-report=term-missing` | 3.552 collected · **90 failed** · coverage `src/prope`: **77%** (19.356 statements, 4.450 missed) |

Run này xác nhận rig Docker/testcontainers và Alembic chain khởi động được sau khi migration `0046` được trả về chain `0045 → 0046`. 90 failures còn lại tập trung ở broker (35), integration (19), architecture (15), contract (15), chaos (5) và security (1); cần được xử lý trước khi có thể tuyên bố suite xanh.

**⚠️ Gap đã biết — CI hiện chưa gate bằng pytest:** `.github/workflows/ci.yml` (từ commit `b30efde`, 12/08) chỉ chạy `ruff` + lint/build/audit SPA rồi deploy EC2. Comment trong workflow ghi *"ruff and the architecture suite are what gate"* nhưng **không có bước pytest nào tồn tại**. Runner self-hosted đã có Docker (job deploy chạy `docker compose up`), nên thêm một bước `uv run pytest -q tests/architecture tests/security` là thay đổi nhỏ và nên làm trước khi nộp.

## 4. Trace tuỳ chọn

Với `LANGFUSE_*` cấu hình, mỗi query eval phát span mang `query_id`, difficulty, stems + scores; extraction span ghi quality/groundedness/tokens/cost/failures. Query text và nội dung prompt **không bao giờ** rời repo (A-020).

## 5. User feedback

Nguồn: [`docs/user-feedback.md`](user-feedback.md) — 5 phản hồi người dùng thật sau khi dùng app (thu 25/08/2026), ghi nguyên văn kể cả phản hồi tiêu cực: mock data ở Overview, PropAI thực thi action không có hiệu lực thật, UI lệch, chi phí lần gọi chưa nhìn thấy được, provider tạo muộn trong màn evaluation không được nhận. Bảng đối chiếu người phản hồi + trạng thái fix nằm trong file nguồn.

## 6. Traceability — map kiểm chứng → cam kết

Mỗi cam kết cốt lõi của Prope được neo vào test có tên gọi rõ ràng trong repo — đọc tên
test là biết nó bảo vệ điều gì (đường dẫn tính từ `tests/`). Bảng dưới chỉ liệt kê các
test **đại diện**; toàn bộ nằm trong suite mục 3.

| Cam kết | Test đại diện | Assert |
|---|---|---|
| **1. Human approval trước production** | `integration/test_release_carries_approval.py` · `integration/test_approve_and_release_combined.py` · `integration/test_break_glass_followup_task.py` | Release chỉ xảy ra trên revision đã Approved; break-glass sinh follow-up task 24h |
| **2. Chỉ Approved được release/resolve** (DB constraint) | `integration/test_released_pointer_constraint.py` · `security/test_gateway_pin_must_be_approved.py` · `integration/test_gateway_resolve_released.py` · `integration/test_gateway_withdrawn_release.py` | Constraint DB chặn released pointer trỏ revision chưa Approved; gateway từ chối pin/resolve bản không Released; withdraw làm gateway ngừng phục vụ |
| **3. Self-approval được ghi nhận, không bị từ chối** | `integration/test_self_approval_is_recorded.py` | Actor tự duyệt revision của chính mình vẫn ghi nhận đầy đủ vào history |
| **4. Private by default** (RLS, not-found thay vì forbidden) | `security/test_private_by_default.py` · `architecture/test_tenant_coverage.py` · `security/test_history_tenant_isolation.py` · `security/test_call_metadata_read_is_private_by_default.py` | RLS phủ mọi schema nghiệp vụ; subject ngoài tầm nhìn trả not-found; call metadata mặc định private |
| Credential mã hoá, không bao giờ trả về | `security/test_credential_never_returned.py` · `security/test_envelope_encryption_roundtrip.py` · `security/test_base_url_ssrf_guard.py` | Không API đọc nào trả credential; envelope encryption roundtrip; base URL bị guard chống SSRF |
| History append-only ở mức DB privilege; actor tombstone | `security/test_append_only_privilege.py` · `security/test_history_is_append_only_by_privilege.py` · `integration/test_actor_attribution_survives_removal.py` | `prope_app` không có DELETE/UPDATE trên history; xoá user không mất vết attribution |
| Secret hiển thị đúng một lần; refusal không lộ thông tin | `security/test_key_secret_shown_once_only.py` · `security/test_key_scope_refusal_cannot_enumerate.py` · `security/test_login_responses_are_indistinguishable.py` | Secret key hiện một lần duy nhất; key-scope refusal giống hệt unknown model; login rate-limit giống hệt sai mật khẩu |
| Nội dung prompt không rò vào log | `architecture/test_no_content_reaches_a_log_line_by_construction.py` · `security/test_no_body_read_path.py` · `security/test_no_history_content_reaches_a_log_line.py` | Không log line chứa nội dung prompt; call body không có read path |
| Ranh giới module (8 bounded contexts) | `architecture/test_no_cross_schema_sql.py` · `architecture/test_gateway_depends_on_four_modules.py` · `architecture/test_access_control_depends_on_one_module.py` · `architecture/test_property_history_depends_on_nothing.py` · `architecture/test_route_table.py` | Không SQL cross-schema; dependency graph đúng ADR; route table phủ đủ action vocabulary |
| Eval cost-guardrail | `evaluation/test_cost_delta_and_summary_rules.py` | Quy tắc cost delta và summary của eval run |
| HITL lifecycle end-to-end | [`eval/evidence/versioning-matrix`](../eval/evidence/versioning-matrix/summary.md) S2–S10 | Mục 2 — promote/block luôn là human decision có ghi nhận |
