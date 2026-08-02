## Coverage Matrix — query phrase → atomic item mapping

Phrases drawn from (a) the verbatim query line and (b) the context block in `query.md` that
resolves its anaphor. Both are in scope; the context block IS the referent of "this problem".

### A. The verbatim query line

| Query phrase (verbatim) | Mapped atomic item(s) | Scope check | Gap? |
|---|---|---|---|
| "how to solve this problem" | Sub-Q1–13 collectively; required_formats: reference architecture, build sequence; headings 1–12 | OK — read as "design + mechanism + sequencing + defence", not merely "list options". Solution-shaped, so architecture AND adoption AND risk all in scope | No |
| "main value" | Scope condition: positioning is FIXED INPUT; heading 1 (what the framing commits you to); heading 12 (where it breaks) | OK — treated as binding constraint the solution must express, with contradicting evidence surfaced as risk rather than re-positioning | No |
| "Sổ tài sản" (asset register/ledger) | Entity: Sổ tài sản prompt; Entity: prompt asset record; Sub-Q1, Sub-Q2; prior-art entities (IT asset register/CMDB, intangible asset accounting, data catalog, model registry, feature store, schema registry) | OK — NOT narrowed to "a database of prompts". Asset framing pulls in ownership, lifecycle, decommission, and valuation, all of which are represented as required_fields | No |
| "prompt" | Scope condition: both code-embedded production prompts AND human-authored prompts in documents/chat | OK — not narrowed to code-embedded system prompts only. Both readings covered | No |
| "của tập đoàn" (of the corporate group) | Scope conditions: internal platform for a single group, multi-product, multi-vendor runtime; Sub-Q11 (adoption inside the organization) | OK — group-wide/cross-product scope preserved; not narrowed to one team or one product | No |

### B. The problem referent (context block)

| Query phrase (verbatim) | Mapped atomic item(s) | Scope check | Gap? |
|---|---|---|---|
| "quản lý & versioning Prompt tập trung" | Sub-Q2 (data model), Sub-Q4 (versioning/release); headings 2 and 4 | OK — BOTH halves kept. "Quản lý" (management: authoring, ownership, organization, lifecycle) is not collapsed into "versioning" | No |
| "nằm rải rác trong code, Google Sheet, Notion" | Entity: scattered prompt sources (code, Sheets, Notion, Drive, chat, shared accounts); Sub-Q3; heading 3 | OK — the three named sources are covered and the set is broadened, not narrowed, to include Drive/chat/shared accounts named elsewhere in the referent | No |
| "không có lịch sử" (no history) | Sub-Q4 (immutable versions, diffing); Entity: versioning layer → required_fields | OK | No |
| "không rollback được" | Sub-Q4 → rollback required_field; heading 4 | OK — rollback treated as a first-class mechanic, incl. decoupling from code deploy | No |
| "không biết phiên bản nào đang chạy production" | Sub-Q4 → "production-version visibility" required_field; Sub-Q8 (parity between what was tested and what runs) | OK — covered from BOTH directions: registry-side visibility and runtime-side parity | No |
| "agent hỗ trợ tạo/sửa/versioning prompt" | Entity: prompt-authoring/improvement agent; Sub-Q9; heading 9 | OK — create/edit/version assistance all named | No |
| "tự đề xuất cải tiến" (auto-propose improvements) | Sub-Q9 → commoditization status + reviewer-overload control | OK — covered including the adversarial reading (it may be a commodity feature, not a differentiator) | No |
| "chạy eval so sánh phiên bản mới với cũ trước khi phát hành" | Sub-Q5; Entity: regression eval subsystem; heading 5 | OK — pre-release comparative eval, not post-hoc monitoring | No |
| "đóng bộ prompt tối ưu dùng chung qua API/SDK" | Sub-Q8; Entity: API/SDK distribution layer; heading 8 | OK — BOTH halves kept: "đóng bộ ... dùng chung" (packaging a shared, curated set — reuse/standardization) AND "qua API/SDK" (the delivery mechanism). Not narrowed to a client library only | No |
| "HITL bắt buộc để duyệt promote phiên bản lên production" | Sub-Q6; Entity: HITL promote gate; heading 6; scope condition (binding constraint) | OK — mandatory-ness preserved; bottleneck risk covered rather than assumed away | No |
| "phân quyền chỉnh sửa theo vai trò" | Sub-Q6; Entity: RBAC → propose-vs-edit separation, cross-team contribution | OK — role model covered, plus the non-obvious case of contribution by people without edit rights | No |
| "eval hồi quy để đảm bảo không giảm chất lượng" | Sub-Q5 → gating thresholds, LLM-as-judge reliability, non-deterministic output; Sub-Q13 (counter-evidence on eval trustworthiness) | OK — the guarantee claim is examined, not assumed | No |
| "cảnh báo thay đổi làm tăng token/chi phí" | Sub-Q7; Entity: token/cost delta alerting and attribution; heading 7 | OK — covers alerting AND the stronger reading (gating), plus measurement accuracy and attribution | No |
| "Prompt Asset Register" (self-defined category) | Sub-Q1; heading 1; prior-art entities | OK | No |
| "non-developer primary user" / personas | Persona entities (non-technical creator, approving manager, consuming developer); scope condition on user priority | OK — all three personas retained in the stated priority order | No |
| "Google Sheet + Notion + Drive + shared accounts" as real incumbent | Entity: incumbent alternative; Sub-Q11; heading 10 | OK — treated as the frame of reference for adoption, with switching-cost analysis | No |
| "three USP pillars" (chaos ingestion / cost gate / two-minute HITL) | Sub-Q3, Sub-Q7, Sub-Q6; headings 3, 6, 7 | OK — one heading each; each pillar gets its own mechanism section rather than a passing mention | No |
| "layer, not a replacement" (sync into Bedrock/Vertex, OTel traces back) | Sub-Q10; Entity list of competing platforms; heading 9; scope condition on multi-vendor runtimes | OK | No |
| "evals bootstrapped from production traffic" | Sub-Q5 → dataset bootstrapping | OK | No |
| "anti-positioning" (no tracing, don't lead with the agent) | Sub-Q9, Sub-Q10; heading 9 | OK — scope boundary respected: the report may explain why observability is out of scope but must not design one | No |
| "VinUni AI20K Build Phase / Demo Day" | Sub-Q12; scope condition (small team, short timeline); heading 11 | OK — delivery constraint is treated as a first-class design input, not a footnote | No |
| "Python + LangGraph + FastAPI + Docker template" | Sub-Q12; scope condition | OK — stack constraint retained; build sequence must be feasible on it | No |
| "enterprise architecture for a real conglomerate" | Scope condition (dual audience); Sub-Q6, Sub-Q8, Sub-Q11 | OK — both readings (demo-feasible AND enterprise-defensible) covered simultaneously | No |

**Result: zero `Gap? = YES` rows.** Decomposition stands as written.

### Scope traps explicitly guarded against

1. **"Sổ tài sản" → "a prompt database".** The asset reading requires ownership, lifecycle,
   decommission and valuation. Narrowing it to storage would silently delete the query's
   stated main value. Guarded by Sub-Q1/Sub-Q2 required_fields and the prior-art entity set.
2. **"quản lý & versioning" → "versioning".** Management (authoring, organizing, owning) is a
   separate half and is where the non-developer persona actually lives.
3. **"prompt" → "production system prompts in code".** The referent explicitly includes prompts
   living in Sheets, Notion and chat, which is the majority of the scattered corpus.
4. **"toàn tập đoàn" → "one product team".** Cross-product, multi-vendor scope is what makes the
   registry distinct from what Bedrock/Vertex already give a single team.
5. **"đóng bộ prompt tối ưu dùng chung" → "an SDK".** The packaging/standardization half
   (a curated shared set) is a different claim from the delivery half (API/SDK) and both are kept.
