# Kiến trúc Prope

Prope là hệ thống quản trị vòng đời prompt cho nhiều workspace: đăng ký và phiên bản hoá prompt, đánh giá, phê duyệt/phát hành có người chịu trách nhiệm, tìm kiếm, và gateway tương thích OpenAI cho ứng dụng tiêu thụ prompt đã phát hành.

Runtime gồm SPA React, một FastAPI application, một worker không có HTTP surface, PostgreSQL có RLS/pgvector và RabbitMQ. Caddy cung cấp một origin duy nhất cho SPA và API. App Agent dùng cấu hình LLM của ứng dụng; provider do workspace cấu hình chỉ được gọi qua `provider-access`.

## Sơ đồ thành phần và luồng dữ liệu

```mermaid
flowchart TB
    person["Người dùng workspace"]
    client["Ứng dụng tiêu thụ prompt<br/>OpenAI-compatible SDK"]
    upstream["Nhà cung cấp LLM<br/>OpenAI-compatible API"]
    app_llm["App Agent LLM + Embeddings<br/>OpenAI / compatible endpoint"]
    langfuse["Langfuse<br/>optional: prompt versions & traces"]

    subgraph edge["Ingress: một origin"]
        caddy["Caddy<br/>SPA static + reverse proxy"]
        spa["React 19 SPA (Vite)<br/>React Router · TanStack Query · Zod"]
    end

    subgraph api["FastAPI app: prope.app"]
        auth["Access Control<br/>session, API key, RBAC/grants"]
        registry["Prompt Registry<br/>prompt property, immutable revisions"]
        release["Release Control<br/>review, approval, release/restore/withdraw"]
        evaluation["Evaluation<br/>suites, runs, deterministic assertions"]
        search["Prompt Search<br/>keyword, semantic search, index request"]
        conversion["Prompt Conversion<br/>TXT/MD/JSON/YAML → canonical XML"]
        chat["Chat Orchestrator<br/>RAG docs, closed tool catalogue, HITL"]
        gateway["Gateway /v1<br/>OpenAI chat completions & models"]
        provider["Provider Access<br/>credential encryption, dispatch, normalize"]
        ledger["Call Ledger<br/>enqueue, pricing, retention settings"]
        history["Property History<br/>append-only audit events"]
    end

    subgraph async["Asynchronous processing"]
        broker["RabbitMQ<br/>call-record queue · search-index queue"]
        worker["Worker: prope.worker<br/>no HTTP endpoint"]
    end

    subgraph data["PostgreSQL 17 + pgvector"]
        db[("Schemas: access, registry, release, evaluation,<br/>provider, ledger, search, chat, history<br/>RLS tenant isolation")]
    end

    subgraph obs["Observability"]
        metrics["/metrics"]
        prometheus["Prometheus<br/>alerts"]
        grafana["Grafana"]
    end

    person -->|"HTTPS / browser"| caddy
    caddy -->|"/"| spa
    spa -->|"cookie-authenticated /api/*"| caddy
    client -->|"API key /v1/*"| caddy
    caddy -->|"/api/*, /v1/*"| auth

    auth --> registry
    auth --> release
    auth --> evaluation
    auth --> search
    auth --> conversion
    auth --> chat
    auth --> provider
    auth --> gateway

    registry <--> release
    registry --> evaluation
    evaluation --> provider
    evaluation --> ledger
    search --> registry
    chat --> search
    chat --> conversion
    chat --> registry
    conversion --> app_llm
    search --> app_llm
    chat --> app_llm
    conversion -.-> langfuse
    search -.-> langfuse
    chat -.-> langfuse

    gateway --> registry
    gateway --> provider
    provider -->|"one upstream attempt<br/>interactive / batch priority"| upstream
    gateway -->|"after response flush"| ledger
    ledger --> broker
    registry -->|"index jobs"| broker
    broker --> worker
    worker --> db

    auth --> db
    registry --> db
    release --> db
    evaluation --> db
    search --> db
    provider --> db
    ledger --> db
    history --> db
    chat --> db

    caddy -->|"/metrics"| metrics
    metrics --> prometheus --> grafana
```

Mũi tên liền thể hiện call/luồng dữ liệu runtime. Mũi tên nét đứt là tích hợp quan sát tuỳ chọn. Các module management gọi `access-control` để xác thực và phân quyền; không module nào tự giữ một bản sao policy.

## Luồng nghiệp vụ chính

### 1. Vòng đời prompt có kiểm soát con người

```mermaid
sequenceDiagram
    actor U as Prompt owner/reviewer
    participant SPA as React SPA
    participant API as FastAPI modules
    participant AC as Access Control
    participant PR as Prompt Registry
    participant EV as Evaluation
    participant PA as Provider Access
    participant RC as Release Control
    participant DB as PostgreSQL + History

    U->>SPA: Tạo prompt hoặc revision
    SPA->>API: /api/v1/* (session cookie)
    API->>AC: may(actor, action, subject)
    AC-->>API: allow/deny
    API->>PR: Ghi prompt/revision bất biến
    PR->>DB: revision + history event (cùng transaction)
    PR-->>SPA: Revision Draft

    U->>SPA: Submit để review
    SPA->>RC: submit revision
    RC->>PR: Đổi trạng thái In review
    RC->>EV: Tạo các eval run cho revision và baseline
    EV->>PA: Dispatch từng case (priority=batch)
    PA->>PA: Decrypt credential trong process
    PA-->>EV: Normalized response + usage / typed failure
    EV->>DB: Case results, deterministic assertions, priced totals

    U->>SPA: Approve rồi Release
    SPA->>RC: Human decision
    RC->>EV: Đọc evidence digest và cost delta
    RC->>PR: Set released revision (chỉ Approved)
    RC->>DB: Approval/release + append-only history
```

`Evaluation` so sánh candidate và released baseline bằng cùng suite. Assertion pass/fail là deterministic; agent chỉ có thể dự thảo dataset/đề xuất, không quyết định release.

### 2. Lưu lượng production qua gateway

```mermaid
sequenceDiagram
    participant C as Client SDK
    participant G as /v1 Gateway
    participant AC as Access Control
    participant PR as Prompt Registry
    participant PA as Provider Access
    participant P as Upstream provider
    participant CL as Call Ledger
    participant MQ as RabbitMQ
    participant W as Worker
    participant DB as PostgreSQL

    C->>G: POST /v1/chat/completions (API key, model)
    G->>AC: Authenticate key + check model scope
    G->>PR: Resolve released revision / approved pin
    G->>G: Compose system prompt + variables + caller messages
    G->>PA: Dispatch one attempt (interactive)
    PA->>P: Chat completion
    P-->>PA: Response/stream + usage
    PA-->>G: Normalized response or typed failure
    alt Upstream fails before first byte and fallback is eligible
        G-->>C: Revision fallback answer, marked as fallback
    else Provider succeeds
        G-->>C: OpenAI-compatible response/stream
    end
    G->>CL: Enqueue call record after response is flushed
    CL->>MQ: Publisher-confirmed message
    MQ->>W: Consume call record
    W->>DB: Persist metadata, best-effort bodies, effective-dated price/spend
```

Nếu publisher confirm thất bại, app dùng direct PostgreSQL fallback: metadata vẫn được ưu tiên bền vững, body có thể bị bỏ và được đếm metric. Gateway không chặn lưu lượng theo spend ceiling; ceiling chỉ từ chối bắt đầu evaluation.

### 3. Công việc nền

```mermaid
flowchart LR
    rabbit["RabbitMQ"] --> ledger_drain["Drain call records<br/>write + pricing"]
    rabbit --> indexer["Prompt-search indexing<br/>extract metadata + embedding"]
    db[("PostgreSQL")] --> eval_claim["Claim eval_run pending"]
    db --> retention["Delete expired call bodies"]
    db --> release_reconcile["Reconcile released pointers<br/>review-task gauges"]
    ledger_drain --> db
    indexer --> agent["App Agent / Embeddings"]
    indexer --> db
    eval_claim --> provider["Provider Access<br/>batch priority"]
    provider --> db
    retention --> db
    release_reconcile --> db
```

Worker được giám sát để chạy lại các job: drain ledger, search indexing, retention, queue depth, eval claim/sweeper và release reconciliation/gauges. Worker không expose HTTP hoặc metrics endpoint; Prometheus scrape `app:8000/metrics`.

## Dữ liệu, bảo mật và ranh giới trách nhiệm

| Vùng dữ liệu | Chủ sở hữu | Luồng/chính sách đáng chú ý |
|---|---|---|
| `access` | Access Control | Workspace, user/session, role/grant, API key; session cho người, API key cho consumer. |
| `registry`, `release`, `history` | Registry, Release Control, Property History | Revision và audit event là append-only; chỉ revision Approved mới được release. |
| `evaluation` | Evaluation | Suite/case/run/result; evidence và cost delta phục vụ quyết định người duyệt. |
| `provider` | Provider Access | Credential mã hoá AES-GCM với KEK ngoài DB; secret không trả về API hoặc log. |
| `ledger` | Call Ledger | Call metadata, body best-effort retention, bảng giá effective-dated và tổng spend. |
| `search` | Prompt Search | Chỉ mục metadata/embedding, cache embedding và vector pgvector. |
| `chat` | Chat Orchestrator | Conversation/message/pending action theo workspace **và** actor. |

Mọi schema nghiệp vụ mang tenant isolation bằng PostgreSQL RLS; runtime `app` và `worker` dùng role ứng dụng, còn migration chạy một lần bằng credential có quyền cao hơn. `property-history` không có API riêng: các module chủ thể kiểm tra quyền rồi đọc activity của chính chúng.

## Triển khai

```mermaid
flowchart TB
    browser["Browser / client SDK"] --> ingress["Caddy :8080 (host)<br/>TLS khi dùng domain"]
    ingress --> web["prope-web image<br/>Caddy + SPA build"]
    ingress --> app["prope-app image<br/>Uvicorn / FastAPI :8000"]
    app <--> pg["PostgreSQL + pgvector"]
    app <--> mq["RabbitMQ"]
    worker["prope-app image<br/>python -m prope.worker"] <--> pg
    worker <--> mq
    prometheus["Prometheus :9090"] --> app
    prometheus --> grafana["Grafana :3000"]
    migrate["One-shot migrate<br/>Alembic + bootstrap roles"] --> pg
```

`docker-compose.yml` điều phối: `postgres`, `rabbitmq`, one-shot `migrate`, `app`, `worker`, `prometheus`, `grafana`, `caddy`. Development overlay thay Caddy bằng Vite dev server có HMR nhưng vẫn proxy cùng các prefix `/api`, `/v1`, `/metrics`, `/healthz`, `/readyz`, nên browser giữ một origin.

## Mã nguồn làm căn cứ

- Composition/runtime: `src/prope/app.py`, `src/prope/worker.py`, `docker-compose.yml`, `Caddyfile`.
- Bounded contexts: `src/prope/{access_control,prompt_registry,release_control,evaluation,provider_access,gateway,call_ledger,prompt_search,prompt_conversion,chat_orchestrator,property_history}`.
- Schema/RLS/migration: `alembic/versions/0001` đến `0021`.
- Frontend: `src/prope-fe/main.tsx`, `App.tsx`, `lib/apiClient.ts` và các feature theo domain.
