---
vault_tag: prompt-asset-register-solution-4fbe59
created: 2026-08-02T02:54:18Z
source: user-prompt
---

on how to solve this problem, with main value is "Sổ tài sản prompt của tập đoàn"

---

## Context resolving "this problem" (the query is anaphoric — this block is the referent, supplied by the orchestrator from the conversation in which the query was issued; it is NOT an addition to the ask)

**The problem, as originally stated by the user (Vietnamese, verbatim):**

> AI Agent quản lý & versioning Prompt tập trung cho toàn tập đoàn
>
> 📍 Thực trạng: Prompt của các sản phẩm AI nằm rải rác trong code, Google Sheet, Notion; mỗi lần chỉnh sửa không có lịch sử, không rollback được, không biết phiên bản nào đang chạy production.
>
> 🎯 Vấn đề: Cần nền tảng có agent hỗ trợ tạo/sửa/versioning prompt, tự đề xuất cải tiến, chạy eval so sánh phiên bản mới với cũ trước khi phát hành và đóng bộ prompt tối ưu dùng chung qua API/SDK.
>
> 🔐 Ràng buộc: HITL bắt buộc để duyệt promote phiên bản lên production; phân quyền chỉnh sửa theo vai trò; eval hồi quy để đảm bảo không giảm chất lượng; cảnh báo thay đổi làm tăng token/chi phí.

**English gloss:** An AI-agent platform for centralized prompt management and versioning across an entire corporate group (a Vietnamese conglomerate). Today prompts for AI products are scattered across source code, Google Sheets, and Notion; edits have no history, cannot be rolled back, and nobody knows which version is running in production. The requested platform needs: an agent that helps create/edit/version prompts, proposes improvements automatically, runs evals comparing new versus old versions before release, and packages an optimized shared prompt set consumable via API/SDK. Hard constraints: mandatory human-in-the-loop (HITL) approval to promote a version to production; role-based edit permissions (RBAC); regression eval to guarantee no quality degradation; and alerts when a change increases token usage / cost.

**The committed product positioning — "main value" named in the query:**

The user has already converged on a positioning, recorded in `docs/product/positioning.md` of this repository. Its core is the Vietnamese phrase **"Sổ tài sản prompt của tập đoàn"** — literally *"the corporate group's prompt asset register/ledger"*. English one-liner: *"The company's prompt asset register — not another AI ops dashboard."* The deliberate strategic choices behind it:

- **Category:** self-defined as **Prompt Asset Register** — an organizational asset ledger plus a prompt release-governance layer. Explicitly NOT LLM observability/tracing, NOT a prompt playground/marketplace, NOT an eval framework.
- **The unit of account is not the trace or span** but *owner, lifecycle, quality, cost* per prompt.
- **Primary user is deliberately the non-developer** (marketer, designer, PM — personas "Minh + Toàn, Des & Mar", self-described as non-technical and "lazy"). The manager who approves promotions ("Toàn") is user #2; the developer who consumes prompts via API/SDK ("Quân") is user #3.
- **The real incumbent being displaced is Google Sheet + Notion + Drive + shared accounts + a chat thread with prompts pasted in** — not Langfuse. The stated win condition is "used more than Google Sheet inside this specific conglomerate," not feature parity with funded LLMOps SaaS.
- **Three USP pillars:** (1) start from the existing chaos — scan repos/Sheets/Notion/Drive/chat exports, extract and cluster near-duplicate prompts, deliver a state-of-the-world map before any migration; (2) cost as a promotion gate, not a retrospective chart — token/cost delta shown while editing and binding on the promote decision; (3) HITL where the approver can decide in two minutes from a single evidence card (consequence-language diff, eval delta, cost delta, blast radius, recommendation).
- **Supporting USPs:** evals bootstrapped from production traffic rather than requiring a pre-built dataset; and being a *layer* that syncs versions down into whatever runtime each product team already uses (Bedrock / Vertex / self-hosted) while pulling traces back via OpenTelemetry — rather than a replacement for those runtimes.
- **Explicit anti-positioning:** does not build tracing/observability; does not lead with "an AI agent that suggests prompt improvements" (already commoditized by Braintrust Loop, PromptLayer, Bedrock).

**Delivery context:** this is a competition/hackathon build (VinUni AI20K Build Phase) with a Demo Day deliverable, built on a Python + LangGraph + FastAPI + Docker template. So both the *product/architecture* answer and its *feasibility under a small-team, short-timeline build* matter.

**What the query is asking for:** how to actually solve the problem above — the design, architecture, mechanism, sequencing and evidence for building it — with "Sổ tài sản prompt của tập đoàn" (the corporate prompt asset register) held fixed as the central value proposition that the solution must express and deliver on.
