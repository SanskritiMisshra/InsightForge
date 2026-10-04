# InsightForge — Architecture Specification (ARCHITECTURE.md)

**Version:** 1.0
**Status:** Authoritative for all backend, worker, infrastructure, and integration work
**Depends on:** `PRD.md`, `DESIGN.md`
**Companion documents:** `DATABASE.md`, `API_SPEC.md`, `ANALYTICS_SPEC.md`, `SQL_SPEC.md`, `POWERBI_SPEC.md`, `REPORTING_SPEC.md`, `AI_SPEC.md`, `SECURITY.md`, `TESTING.md`, `DEPLOYMENT.md`, `DECISIONS.md`

> If this document conflicts with `PRD.md`, the conflict must be identified and resolved before implementation continues (PRD §127). Any architectural change must be recorded in `DECISIONS.md` (PRD §126).

---

# 1. Purpose and Scope

This document defines **how** InsightForge is built: system boundaries, services, data flow, technology choices, module structure, the analytics engine, the job pipeline, storage, security boundaries, and operational concerns.

It translates the PRD's principles into enforceable structural rules:

| PRD Principle | Architectural Consequence |
|---|---|
| Accuracy over appearance (§5.1) | A single deterministic analytics engine owns all numbers; UI and reports never compute metrics |
| Evidence before explanation (§5.2) | Every metric is persisted with its calculation, SQL, dataset version, and pipeline version |
| AI explains; analytics calculates (§5.3, §97) | LLM sits **downstream** of verified metrics, behind a number-verification guard |
| Reproducibility (§5.4, §95) | Immutable dataset versions + versioned pipeline + recorded configuration = replayable runs |
| Transparency (§5.5, §117) | Cleaning log, lineage graph, audit log are first-class data, not log files |
| Extensibility (§5.6, §121–122) | Domain plugin architecture; retail is the first plugin, not hard-coded into the core |

---

# 2. Architectural Drivers

## 2.1 Functional drivers
- Upload → validate → profile → clean → analyze → insight → report/deck, end to end (PRD §10).
- Retail/E-Commerce domain in V1 with partial-analysis tolerance (PRD §65).
- Safe SQL analytics over user data (PRD §46–48).
- Generated artifacts: PDF, DOCX, PPTX, Power BI-ready model (PRD §55–59).

## 2.2 Quality attributes (ranked)

| Rank | Attribute | Target / Mechanism |
|---|---|---|
| 1 | **Correctness** | Deterministic engine, golden-dataset tests, single source of truth |
| 2 | **Security & tenant isolation** | Ownership enforced in a single authorization layer; sandboxed SQL |
| 3 | **Reproducibility & auditability** | Immutable versions, versioned pipeline, audit events |
| 4 | **Reliability** | Idempotent, retryable, stage-isolated jobs |
| 5 | **Responsiveness** | Async processing; aggregation before charting; server-side pagination |
| 6 | **Scalability** | Stateless API; horizontally scalable workers; object storage for data |
| 7 | **Maintainability / Extensibility** | Layered modules, domain plugins, typed contracts |

## 2.3 Constraints
- Stack fixed by PRD: Next.js + TypeScript, FastAPI, Python analytics engine, PostgreSQL, Redis, Celery.
- No enterprise warehouse, no streaming, no autonomous ML in V1 (PRD §9).
- Datasets never fully loaded into the browser (PRD §20, §75).
- Raw data is immutable (PRD §29).

---

# 3. System Context

```text
                      ┌───────────────────────────┐
                      │          End User         │
                      └─────────────┬─────────────┘
                                    │ HTTPS
                      ┌─────────────▼─────────────┐
                      │       InsightForge        │
                      │  (Web App + API + Workers)│
                      └──┬─────────┬──────────┬───┘
                         │         │          │
              ┌──────────▼──┐  ┌───▼──────┐  ┌▼────────────────┐
              │ Google OAuth │  │ LLM API  │  │ Object Storage  │
              │  (identity)  │  │(optional)│  │ (S3-compatible) │
              └──────────────┘  └──────────┘  └─────────────────┘

   Out of scope for V1: direct Power BI tenant publishing (PRD §9.4),
   enterprise warehouses, streaming sources.
```

External dependencies:

| System | Purpose | Failure impact |
|---|---|---|
| Google OAuth | Social login | Email/password login remains available |
| LLM provider | Explanations/summaries only (PRD §53) | Platform degrades to deterministic templates; no analytics are lost |
| S3-compatible object storage | Raw/clean datasets and artifacts | Uploads and artifact generation unavailable; read-only analytics from cache may continue |

---

# 4. High-Level Architecture

## 4.1 Container view

```text
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                               Browser                                   │
 │                    Next.js UI (React, TS, Tailwind)                     │
 └───────────────┬─────────────────────────────────────────────────────────┘
                 │ HTTPS (cookies, same-site)         ▲ SSE (job progress)
 ┌───────────────▼─────────────────────────────────────┴───────────────────┐
 │  Next.js server (SSR/BFF)  — renders pages, proxies /api/* to FastAPI   │
 └───────────────┬─────────────────────────────────────────────────────────┘
                 │ HTTP (internal network)
 ┌───────────────▼─────────────────────────────────────────────────────────┐
 │                          FastAPI  (Backend API)                         │
 │  auth · projects · datasets · analyses · metrics · insights · sql ·     │
 │  reports · powerbi · exports · notifications · admin                    │
 └───────┬──────────────┬───────────────────────┬──────────────────────────┘
         │              │ enqueue               │ presigned URLs / streams
         │              ▼                       ▼
         │        ┌───────────┐        ┌──────────────────────┐
         │        │   Redis   │        │   Object Storage     │
         │        │ broker +  │        │ raw/ cleaned/ ...    │
         │        │ progress  │        └──────────▲───────────┘
         │        └─────┬─────┘                   │
         │              │ consume                 │ read/write
         │        ┌─────▼─────────────────────────┴───────────┐
         │        │          Celery Workers                    │
         │        │  Analytics Pipeline · SQL sandbox ·        │
         │        │  Report/Deck/PowerBI generators            │
         │        └─────┬─────────────────────────────────────┘
         │              │ metadata, metrics, logs
 ┌───────▼──────────────▼──────┐
 │         PostgreSQL           │   (application DB: metadata, metrics,
 │   users · projects · runs    │    insights, audit — NOT the analytical
 │   metrics · insights · ...   │    data store)
 └──────────────────────────────┘
```

## 4.2 Key structural decisions (summary)

| # | Decision | Rationale |
|---|---|---|
| A1 | **Modular monolith backend** (one FastAPI codebase, one analytics-engine package, separate worker process) | Right-sized for V1; strict module boundaries allow later extraction |
| A2 | **Analytics Engine is a pure Python library**, framework-agnostic, imported by both API (light calls) and workers (pipeline) | Testable in isolation; deterministic; no web/DB coupling |
| A3 | **PostgreSQL = system of record for metadata/metrics; object storage = system of record for data** | PRD §68–69 |
| A4 | **Analytical SQL runs on DuckDB over Parquet** in a sandboxed worker context, not on application Postgres | Isolation from app tables (PRD §48), fast columnar analytics, trivially read-only |
| A5 | **Datasets stored as Parquet** after ingestion; original upload kept byte-for-byte | Immutable raw + efficient analytics |
| A6 | **Dataset versions are immutable Parquet snapshots**; every run references one | PRD §29–30, §95 |
| A7 | **Metrics are persisted, typed records** consumed by every downstream generator | PRD §49, §60, §96 |
| A8 | **LLM access via a provider-agnostic gateway with number-verification guard** | PRD §51, §97 |
| A9 | **Cookie-based sessions issued by FastAPI** (httpOnly, SameSite) with Argon2id password hashing | PRD §12; avoids token-in-localStorage risk |
| A10 | **Progress delivered via SSE with polling fallback** | PRD §63 |
| A11 | **Domain plugin registry** (`domains/retail`, …) | PRD §121–122 |

Full rationale and alternatives for each are recorded as ADRs in `DECISIONS.md` (see §22).

---

# 5. Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js (App Router), React, TypeScript (strict), Tailwind CSS | Per `DESIGN.md`; Radix primitives; TanStack Query for server state; Zod for runtime validation |
| Charts | Recharts or ECharts behind a single `ChartFrame` | Decision recorded in `DECISIONS.md` |
| Backend API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x (async), Alembic | OpenAPI is generated and is the contract source |
| Auth | Authlib (Google OIDC), `argon2-cffi`, signed session cookies / server-side sessions in Redis | See §12 |
| Task queue | Celery 5, Redis broker | Worker pools per queue (§9) |
| Analytics | Polars (primary dataframe engine), pandas (compat only), NumPy, SciPy (statistics), DuckDB (SQL), PyArrow (Parquet) | Polars chosen for memory efficiency and lazy execution |
| SQL safety | `sqlglot` (AST parsing/validation) + DuckDB read-only connection | See §10 |
| Database | PostgreSQL 16 | App metadata; row-level ownership checks in service layer |
| Cache / state | Redis 7 | Job state, progress, SSE pub/sub, rate limits, short-lived caches |
| Object storage | S3-compatible (MinIO in dev; S3/R2/GCS-interop in prod) via `boto3`/`aioboto3` | |
| Reporting | `python-pptx` (PPTX), `python-docx` (DOCX), HTML→PDF via WeasyPrint (or Playwright-Chromium), Matplotlib/Plotly+Kaleido for static charts | See §14 |
| Observability | OpenTelemetry (traces/metrics), structlog (JSON logs), Prometheus-compatible metrics, Sentry-compatible error reporting | |
| Testing | pytest, hypothesis (property tests), pytest-postgresql/testcontainers, Playwright (E2E), Vitest, axe | See §20 |
| Packaging | Docker, Docker Compose (dev), container orchestration (prod, see `DEPLOYMENT.md`) | |
| Tooling | `uv` or Poetry (Python), pnpm (Node), Ruff + mypy (Python), ESLint + Prettier (TS), pre-commit | |

**Dependency discipline (PRD §126):** adding a runtime dependency requires a one-line justification in the PR and, if architectural, a `DECISIONS.md` entry.

---

# 6. Repository Structure

Monorepo.

```text
insightforge/
├── apps/
│   ├── web/                         # Next.js frontend
│   │   ├── app/                     # routes (see PRD §71)
│   │   ├── components/{ui,features}/
│   │   ├── lib/{api,format,auth}/
│   │   └── tests/
│   └── api/                         # FastAPI service
│       ├── insightforge_api/
│       │   ├── main.py
│       │   ├── core/                # config, logging, security, errors, deps
│       │   ├── auth/                # routes, services, schemas
│       │   ├── projects/
│       │   ├── datasets/
│       │   ├── analyses/
│       │   ├── metrics/
│       │   ├── insights/
│       │   ├── sql/
│       │   ├── reports/
│       │   ├── powerbi/
│       │   ├── exports/
│       │   ├── notifications/
│       │   ├── audit/
│       │   └── db/                  # models, repositories, migrations (alembic)
│       └── tests/
├── packages/
│   ├── analytics_engine/            # PURE Python library (no FastAPI/Celery imports)
│   │   ├── insightforge_engine/
│   │   │   ├── ingest/              # readers, validators, type inference
│   │   │   ├── profiling/
│   │   │   ├── semantics/           # semantic column detection
│   │   │   ├── quality/             # scoring, missingness, duplicates, outliers
│   │   │   ├── cleaning/            # operations registry + log
│   │   │   ├── eda/
│   │   │   ├── stats/               # correlation, distributions
│   │   │   ├── metrics/             # metric registry, definitions
│   │   │   ├── sqlgen/              # SQL templates + validation
│   │   │   ├── segmentation/        # rule-based + RFM
│   │   │   ├── insights/            # rule engine
│   │   │   ├── recommendations/
│   │   │   ├── charts/              # chart-spec selection (not rendering)
│   │   │   ├── powerbi/             # star schema + measures builders
│   │   │   ├── pipeline/            # stage definitions, DAG, context
│   │   │   ├── domains/
│   │   │   │   ├── base.py          # Domain protocol
│   │   │   │   └── retail/          # V1 domain plugin
│   │   │   └── version.py           # PIPELINE_VERSION
│   │   └── tests/                   # golden datasets live here
│   ├── report_generators/           # PDF/DOCX/PPTX builders (consume metrics only)
│   ├── llm_gateway/                 # provider abstraction + guard
│   └── shared_schemas/              # Pydantic models shared by API + engine
├── workers/
│   └── celery_app/                  # task definitions, queues, routing, signals
├── infra/
│   ├── docker/                      # Dockerfiles
│   ├── compose/                     # docker-compose.{dev,test}.yml
│   └── deploy/                      # prod manifests / IaC
├── docs/                            # PRD.md, DESIGN.md, ARCHITECTURE.md, …
├── scripts/
└── .github/workflows/
```

**Dependency rules (enforced by import-linter in CI):**

```text
apps/web          → (HTTP only) apps/api
apps/api          → packages/analytics_engine (read-only helpers), shared_schemas, llm_gateway
workers           → packages/* , apps/api db layer (repositories)
analytics_engine  → shared_schemas ONLY        (never imports api, workers, celery, sqlalchemy, fastapi)
report_generators → shared_schemas ONLY        (reads verified metrics, never recalculates)
llm_gateway       → shared_schemas ONLY
```

The analytics engine being free of web/DB dependencies is **non-negotiable**: it is what makes numerical correctness testable and reproducible.

---

# 7. Backend API Architecture

## 7.1 Layering

```text
 HTTP Request
     ↓
 Router            (FastAPI path ops: parse, auth dependency, response model)
     ↓
 Service layer     (use-cases; authorization; transactions; emits audit events)
     ↓
 Repository layer  (SQLAlchemy queries; ALWAYS scoped by owner_id)
     ↓
 PostgreSQL

 Service layer ──► Task dispatcher ──► Celery/Redis      (long work)
 Service layer ──► Storage client  ──► Object storage    (files)
```

Rules:
- **Routers contain no business logic.** They validate input and call services.
- **Services own authorization and transactions.** They call `authorize(user, resource, action)` before any data access.
- **Repositories never accept an unscoped ID lookup** for user-owned resources; every query includes `owner_id` (or joins through project ownership). An unscoped `get_by_id` for owned entities is forbidden by convention and lint rule.
- **No analytics in the API process** beyond trivial, bounded reads (e.g., fetching persisted metrics, paginated previews). Anything proportional to dataset size runs in workers.

## 7.2 API conventions (PRD §87–89)

- Base path: `/api/v1`.
- JSON, `snake_case` fields, ISO-8601 UTC timestamps, IDs as UUIDv7 (time-ordered) strings.
- Resource-oriented, nouns plural: `/projects`, `/projects/{id}/datasets`, `/analysis-runs/{id}`.
- Pagination: cursor-based for large/time-ordered lists, `limit` (default 25, max 100); offset allowed for small admin lists. Response envelope: `{ "items": [...], "next_cursor": "...", "total": 125430? }` (`total` optional and potentially approximate).
- Error format (RFC 7807-style):

```json
{
  "error": {
    "code": "DATASET_INVALID_STRUCTURE",
    "message": "The file could not be read as a valid CSV.",
    "details": [{ "field": "file", "issue": "inconsistent_column_count" }],
    "request_id": "01J..."
  }
}
```

- Error `code`s are a closed enum shared with the frontend (maps to copy in `DESIGN.md` §6.6). Stack traces are never returned (PRD §64, §82).
- Idempotency: `POST` endpoints that start jobs accept an `Idempotency-Key` header and also derive a **deterministic run key** (see §9.5).
- Versioning: URL-prefixed (`/api/v1`); breaking changes require `/api/v2`.
- OpenAPI is generated from Pydantic models and is published to the frontend client generator; `API_SPEC.md` documents semantics beyond the schema.

## 7.3 Primary resource map

| Resource | Key operations |
|---|---|
| `auth` | register, login, logout, google start/callback, me, password reset |
| `projects` | CRUD, archive (soft delete), list with filters |
| `datasets` | create upload session, finalize upload, list, get, delete (dependency check) |
| `dataset-versions` | list, get, lineage, preview (paginated), schema, download |
| `columns` | list, update semantic mapping (creates new analysis config, not new raw data) |
| `analysis-runs` | create (idempotent), get, list, cancel, retry, stage logs |
| `quality-reports` | get by run |
| `cleaning-operations` | list by version, preview impact, apply (creates version) |
| `metrics` | list/filter by run, get with evidence |
| `insights` / `recommendations` | list/filter by run, get with evidence |
| `sql` | list questions, execute (sandboxed), history, get result page |
| `reports` | generate (pdf/docx/pptx), list, download link, delete |
| `powerbi` | generate model, get spec, download package |
| `exports` | cleaned data, results, SQL results |
| `notifications` | list, mark read |
| `events/stream` | SSE for run progress |

## 7.4 Real-time progress

- Workers publish stage events to Redis Pub/Sub channel `run:{run_id}`; the API exposes `GET /api/v1/analysis-runs/{id}/events` as **Server-Sent Events**.
- The authoritative state is in PostgreSQL (`jobs`, `analysis_runs`, `stage_runs`); Redis holds transient progress. If SSE fails or is unavailable, the client **falls back to polling** `GET /analysis-runs/{id}` every 2s with backoff.
- SSE connections are authenticated with the session cookie and re-authorize ownership on connect.

---

# 8. The Analytics Engine

The engine is the heart of the product and the **only** producer of numerical truth (PRD §96).

## 8.1 Design rules

1. **Pure and deterministic.** Same inputs (dataset version bytes + config + `PIPELINE_VERSION`) → identical outputs. No wall-clock, randomness, or network in analytic paths. Any stochastic method (e.g., sampling for a scatter) uses a **seed derived from the run key**.
2. **Explicit typing.** Inputs/outputs are Pydantic models from `shared_schemas`.
3. **No I/O coupling.** The engine reads/writes through narrow interfaces (`DataReader`, `ArtifactWriter`) injected by the worker.
4. **Fail loud, degrade gracefully.** A module reports `Unavailable(reason)` when prerequisites are missing; it never fabricates output (PRD §65, §116).
5. **Precision preserved.** Internal arithmetic uses full-precision `float64` (or `Decimal` for monetary aggregation where configured); rounding occurs only at presentation (PRD §114).
6. **Every output carries provenance:** `dataset_version_id`, `pipeline_version`, `config_hash`, `calculation` text, optional `sql`.

## 8.2 Module map

| Module | Responsibility | PRD |
|---|---|---|
| `ingest` | Format readers (CSV/XLSX/JSON), encoding detection, structural validation, conversion to Parquet | §17–20, §115 |
| `profiling` | Dataset- and column-level statistics | §21 |
| `semantics` | Type detection, semantic role detection (rules first, optional LLM suggestion, then validation) | §22–23 |
| `quality` | Completeness/Consistency/Validity/Uniqueness scoring, missingness severity, duplicate and outlier detection | §24–26, §35 |
| `cleaning` | Registry of safe, logged, versioned operations | §27–30 |
| `eda` | Numerical/categorical/time analyses, correlation, chart-spec selection | §31–34 |
| `domains.retail` | Sales, customer, product, discount, payment, geographic, time metrics; segmentation; RFM; Power BI model builder; insight rules | §36–45, §123 |
| `sqlgen` | Question → parameterized SQL templates; validation | §46–48 |
| `metrics` | Metric registry, metric record construction, evidence linking | §49 |
| `insights` / `recommendations` | Rule-based generation from metrics | §50–52 |
| `powerbi` | Star schema export, DAX measure definitions, dashboard spec | §55–57 |

## 8.3 Pipeline model

The pipeline is a **linear DAG of idempotent stages**, each with declared inputs/outputs and prerequisites. Stage names align with PRD §61.

```text
VALIDATING → PROFILING → CLEANING → TRANSFORMING → EDA → SQL_ANALYSIS
          → INSIGHT_GENERATION → POWERBI_PREPARATION
          → REPORT_GENERATION → PRESENTATION_GENERATION → COMPLETED

(QUEUED precedes; UPLOADING is handled by the upload flow; FAILED is terminal.)
```

Stage contract:

```python
class Stage(Protocol):
    name: StageName
    requires: set[Capability]          # e.g. {"dataset_valid"}
    produces: set[Capability]          # e.g. {"profile", "column_types"}

    def plan(self, ctx: RunContext) -> StageApplicability:
        """Return Available | Unavailable(reason) — decided deterministically from ctx."""

    def run(self, ctx: RunContext) -> StageResult:
        """Pure computation + writes via injected writers. Must be idempotent."""
```

- **`RunContext`** holds: run id/key, dataset version handle, semantic mapping, domain plugin, config, injected reader/writers, seed, `PIPELINE_VERSION`.
- **`StageResult`** contains persisted outputs + `StageLog` (counts, duration, warnings).
- Stage `plan()` allows **partial analysis**: unavailable sub-modules are recorded with reasons and the pipeline continues (PRD §65). Only structurally fatal conditions (invalid/empty dataset) fail the run.
- Report and deck stages are **optional**; they run when the user requests them (or per project setting) and consume only persisted metrics.

## 8.4 Metric registry and the metric record

All numbers are produced through the registry:

```python
@metric(
    name="total_revenue",
    domain="retail",
    requires={Role.REVENUE},
    unit=Unit.CURRENCY,
    calculation="SUM(revenue)",
)
def total_revenue(ctx) -> MetricValue: ...
```

Persisted record (PRD §49):

```json
{
  "id": "01J...",
  "run_id": "01J...",
  "metric_name": "total_revenue",
  "value": 8420312.48392,
  "unit": "currency",
  "currency": "INR",
  "dimensions": {},
  "source": "transactions",
  "calculation": "SUM(revenue)",
  "sql_query_id": "01J...",
  "dataset_version_id": "01J...",
  "pipeline_version": "1.0.3",
  "config_hash": "sha256:…",
  "computed_at": "2026-10-03T14:22:11Z"
}
```

Rules:
- Dimensional metrics (e.g., revenue by category) are stored as one record per dimension value or as a structured `series` payload, with the same provenance.
- Metric names are a stable, documented vocabulary in `ANALYTICS_SPEC.md`. Changing a metric's definition **bumps `PIPELINE_VERSION`**.
- **Consumers (insights, recommendations, charts, reports, decks, Power BI measures, LLM prompts) reference metrics by ID only.** They may never recompute a figure (PRD §60, §96).

## 8.5 Semantic detection

Pipeline: (1) deterministic type inference → (2) rule-based role matching (name patterns, value patterns, cardinality, domain rules) → (3) optional LLM suggestion for ambiguous columns (via `llm_gateway`, output constrained to the role enum) → (4) **validation** (type/cardinality/consistency checks) → (5) user-visible mapping with confidence and an editable override (PRD §23). The final mapping that drives analysis is always the validated one, persisted per dataset version.

## 8.6 Cleaning engine

- Operations are registered classes: `RemoveExactDuplicates`, `StandardizeTypes`, `NormalizeCategories`, `HandleMissing(strategy)`, `ParseDates`, `RemoveInvalidRecords(rule)`, `NormalizeText`, `StandardizeNumerics`.
- Each operation implements `preview(df) -> ImpactSummary` and `apply(df) -> (df', CleaningLogEntry)`.
- Operations are **pure transforms on a Polars LazyFrame**; applying a set produces a **new dataset version** (Parquet) plus ordered `cleaning_operations` rows with before/after counts, reason, and timestamp (PRD §28).
- Defaults are conservative: outliers and near-duplicates are **flagged, not removed** (PRD §26, §35). Removal requires an explicit user choice and creates a new version.

## 8.7 Domain plugin architecture (PRD §121–122)

```python
class Domain(Protocol):
    key: str                                    # "retail"
    semantic_roles: set[Role]
    required_fields: dict[Module, set[Role]]    # per analysis module
    optional_fields: dict[Module, set[Role]]

    def metrics(self) -> list[MetricDef]: ...
    def sql_questions(self) -> list[SqlQuestion]: ...
    def visualizations(self) -> list[VizRule]: ...
    def insight_rules(self) -> list[InsightRule]: ...
    def recommendation_rules(self) -> list[RecommendationRule]: ...
    def powerbi_model(self, ctx) -> PowerBIModelSpec: ...
```

- Domains register via an entry-point style registry (`domains/__init__.py`). V1 registers only `retail`.
- Module availability is computed from `required_fields` against the validated mapping, producing the `Available / Unavailable(reason)` states displayed in the UI (PRD §66).
- Adding a domain must require **no changes** to ingest, profiling, quality, cleaning, storage, jobs, or the API — only a new package under `domains/`.

## 8.8 Retail domain (V1)

Modules and their prerequisites:

| Module | Required roles | Notes |
|---|---|---|
| Sales | `REVENUE` (or `PRICE`+`QUANTITY`) | Revenue derivation rule documented; derived revenue is labeled as derived |
| Orders / AOV | `TRANSACTION_ID`, `REVENUE` | Order grain definition in `ANALYTICS_SPEC.md` |
| Customers | `CUSTOMER_ID` | New vs returning needs `PURCHASE_DATE` |
| RFM | `CUSTOMER_ID`, `PURCHASE_DATE`, `REVENUE` | Reference date = max(date)+1 day unless configured |
| Segmentation | `CUSTOMER_ID`, `REVENUE` (+ date for At Risk) | Rules versioned and displayed |
| Products | `PRODUCT_ID` or `PRODUCT_NAME`, `REVENUE`/`QUANTITY` | |
| Discount | `DISCOUNT`, `REVENUE` | Association only |
| Payment | `PAYMENT_METHOD` | |
| Geography | `COUNTRY`/`STATE`/`CITY` | |
| Time | `PURCHASE_DATE`, `REVENUE` | Growth only when comparison period is complete |

## 8.9 Insight and recommendation engines

- **Rule-based, template-driven.** Each `InsightRule` declares: input metric IDs, trigger condition (e.g., share ≥ threshold), title/description templates with **placeholders bound to metric IDs**, confidence logic, and supporting SQL reference.
- Rendering substitutes values from the metric records; free-form numbers cannot enter text.
- `confidence` is computed from data sufficiency (sample size, missingness of used columns, effect size) with documented thresholds (`ANALYTICS_SPEC.md`).
- Recommendations are bound to one or more insights and use qualified language templates ("Investigate…", "Consider…"); causal verbs are blocked by a template linter (CI test).
- The LLM may paraphrase **already-rendered** text (§11) but never creates insights.

---

# 9. Job Processing Architecture

## 9.1 Components

```text
 API ──enqueue──► Redis (broker) ──► Celery Workers
                                         │ writes
                       PostgreSQL ◄──────┘ (jobs, stage_runs, metrics …)
                       Redis Pub/Sub ◄─────  progress events ──► API SSE ──► Browser
```

## 9.2 Queues and worker pools

| Queue | Work | Concurrency | Notes |
|---|---|---|---|
| `ingest` | Validation, Parquet conversion | CPU-bound, small pool | Memory-bounded; streaming where possible |
| `analysis` | Profiling, cleaning, EDA, metrics, SQL | CPU/memory-heavy | Per-task memory limits; `acks_late` |
| `generate` | Reports, decks, Power BI packages, exports | Moderate | Isolated because Chromium/WeasyPrint are heavy |
| `light` | Notifications, cleanup, retention | High | Short tasks |

Separate queues prevent report generation from starving analytics, and let each pool scale independently (PRD §86).

## 9.3 Stage execution and persistence

- One Celery task orchestrates a run by executing stages sequentially (or chaining one task per stage for stronger isolation; V1 default: **one task per stage chained** so a stage can be retried independently).
- Each stage writes a `stage_runs` row: `status`, `started_at`, `finished_at`, `duration_ms`, `counts`, `warnings`, `error_code`.
- On stage success, outputs are committed **atomically** (DB transaction + artifact write with a temp key renamed on commit) before the next stage starts.
- A run's overall status is derived from stage statuses and mirrored to `analysis_runs.status` (PRD §61, §102).

## 9.4 Retry and failure handling (PRD §64, §103)

| Failure type | Behavior |
|---|---|
| Transient infra (network, broker blip, storage 5xx) | Automatic retry with exponential backoff + jitter, max 3 |
| Data/validation failures | **No auto-retry**; stage marked FAILED with user-readable `error_code` + reason |
| Worker crash / OOM | `acks_late` + `reject_on_worker_lost` → task redelivered; idempotent stages make this safe |
| Poison tasks | After max retries, run marked FAILED; dead-letter record kept for operators |
| Time limits | Soft limit (graceful cancel) + hard limit per queue; surface "took too long" with guidance |

User-visible retry (`POST /analysis-runs/{id}/retry`) re-runs from the **first non-completed stage**, reusing completed stage outputs when their inputs' hashes are unchanged.

## 9.5 Idempotency (PRD §104)

- **Run key** = `sha256(dataset_version_id ‖ config_hash ‖ PIPELINE_VERSION ‖ domain_key ‖ semantic_mapping_hash)`.
- Unique constraint on `(project_id, run_key)` where status ∈ {QUEUED, RUNNING, COMPLETED}. Creating a run with an existing key returns the existing run (HTTP 200 + `Location`), never a duplicate.
- Stage outputs are keyed by `(run_id, stage)` with `UPSERT`/replace semantics so replays do not duplicate metrics, insights, or files.
- Report generation is keyed by `(run_id, format, template_version, section_selection_hash)`.

## 9.6 Cancellation

`POST /analysis-runs/{id}/cancel` sets a cancel flag in Redis and DB; stages check the flag at safe checkpoints and exit cleanly, leaving prior committed outputs intact. Status → `CANCELLED`.

## 9.7 Concurrency control

- Per-user limits: max concurrent active runs (configurable, default 2) and per-queue rate limits.
- Per-dataset-version advisory lock prevents two cleaning/transform operations from creating conflicting child versions.

---

# 10. Data Architecture

## 10.1 Storage layout (PRD §68)

```text
s3://insightforge-{env}/
  raw/{owner_id}/{dataset_id}/original/{checksum}.{ext}      # byte-identical, write-once
  raw/{owner_id}/{dataset_id}/ingested/v1.parquet            # normalized columnar copy of v1
  cleaned/{owner_id}/{dataset_id}/v{n}.parquet               # version n (n ≥ 2)
  derived/{owner_id}/{dataset_id}/v{n}/{run_id}/...          # run-scoped analytical tables (rfm, segments…)
  reports/{owner_id}/{project_id}/{run_id}/{format}/{file}
  presentations/{owner_id}/{project_id}/{run_id}/{file}
  exports/{owner_id}/{project_id}/{export_id}/{file}
  powerbi/{owner_id}/{project_id}/{run_id}/{package}.zip
  tmp/...                                                    # lifecycle-expired
```

- Object-lock/“write-once” semantics on `raw/.../original` (bucket policy + app-level refusal to overwrite). **Cleaning never touches raw** (PRD §29).
- Keys include `owner_id` to simplify isolation audits and per-user retention/deletion.
- Server-side encryption at rest; TLS in transit.
- The database stores **references and metadata only** (object key, size, checksum, version), never dataset bodies (PRD §68).

## 10.2 Upload flow

```text
1. POST /datasets/uploads            → API validates request (name, size cap, extension) 
                                       creates dataset row (UPLOADED) + presigned multipart URL
2. Browser uploads directly to object storage (progress shown client-side)
3. POST /datasets/{id}/finalize      → API verifies object exists, size, checksum (SHA-256)
                                       enqueues ingest task (VALIDATING)
4. Worker (ingest queue):
     a. Sniff MIME/magic bytes; check extension ↔ content
     b. Safe parse in a resource-limited process (row/col/size/time limits; zip-bomb & XML-entity protection for XLSX)
     c. Encoding detection (CSV), JSON structure checks (records/NDJSON)
     d. Reject empty/corrupt datasets with explicit reason codes (PRD §18, §115)
     e. Write ingested Parquet (v1), extract schema, row/col counts
     f. Persist metadata + dataset_version v1; status VALID
5. Auto-trigger analysis run (or wait for user, per project setting)
```

Direct-to-storage upload avoids proxying large files through the API (scalability, PRD §75–76). The maximum upload size is a configurable setting (`MAX_UPLOAD_BYTES`), enforced at presign time, at finalize, and in the worker.

## 10.3 Dataset versioning and lineage (PRD §29–30, §118)

```text
dataset ─┬─ version 1  (ingested original; immutable)
         ├─ version 2  (parent=1, via cleaning_operations[…])
         └─ version 3  (parent=2, via transformation)

analysis_run ──references──► exactly one dataset_version
```

- Versions are **append-only**; the content hash (`sha256` of Parquet bytes) is recorded and verified when loaded by a worker.
- Lineage is stored as `dataset_versions.parent_version_id` + `created_by_operation_set_id`, enabling the UI lineage graph.
- Semantic mappings and analysis configs are versioned per dataset version; changing a mapping produces a **new run key**, not a mutation of past runs.

## 10.4 Application database (PostgreSQL)

Core entities (PRD §69; DDL in `DATABASE.md`):

```text
users ── projects ── datasets ── dataset_versions ── dataset_columns
                │                       │
                │                       └── cleaning_operations
                └── analysis_runs ── stage_runs
                         ├── data_quality_reports
                         ├── metrics ── (sql_queries)
                         ├── insights ── recommendations
                         ├── reports
                         ├── presentations
                         └── powerbi_models
jobs, audit_events, notifications, sessions, idempotency_keys
```

Conventions:
- UUIDv7 primary keys; `created_at/updated_at` (UTC `timestamptz`); soft-delete (`deleted_at`) for projects (PRD §108).
- Foreign keys with `ON DELETE RESTRICT` for dataset/version dependencies (PRD §109); deletes are explicit service operations that check dependencies.
- Indexes on `(owner_id, created_at)`, `(project_id, status)`, `(run_id, metric_name)`, `(dataset_id, version)`; GIN on JSONB payloads only where queried.
- JSONB used for variable structures (metric `dimensions`, stage `counts`), never for core relational data.
- Migrations via Alembic; every migration reversible or explicitly flagged; run in CI against a clean DB.

## 10.5 Analytical SQL environment (PRD §46–48)

**Decision:** SQL analytics run on **DuckDB** against run-scoped Parquet snapshots inside the worker, **not** on the application PostgreSQL.

```text
Worker (sql sandbox)
  ├─ opens in-memory DuckDB connection (no persistent file, no network extension, no file-system extension)
  ├─ registers views over the *specific dataset version* Parquet
  │     transactions, customers_dim, products_dim, date_dim, …  (derived per domain)
  ├─ sets: read-only, memory_limit, threads, statement timeout, max result rows
  └─ executes validated SQL → returns capped, paginated result + timing
```

Why:
- **Isolation (PRD §48):** application tables (users, sessions, other tenants) are physically unreachable.
- **Performance:** columnar analytics on Parquet without moving data into Postgres.
- **Reproducibility:** query + dataset version hash fully determine the result.
- **Simplicity:** no per-run schemas or load jobs in Postgres.

### SQL safety layers (defense in depth)

1. **AST validation (`sqlglot`)**: parse → must be a **single** `SELECT`/`WITH … SELECT` statement; reject DDL/DML (`DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE, COPY, ATTACH, INSTALL, LOAD, PRAGMA, SET, CALL, EXPORT`), multiple statements, comments that hide statements, and any reference outside the **allow-listed relations** and functions. File-reading table functions (`read_csv`, `read_parquet`, `glob`, …) and `httpfs` are blocked.
2. **Parameterization:** generated/templated SQL binds user-supplied values as parameters, never string-concatenated (PRD §82).
3. **Engine configuration:** DuckDB opened `read_only`/in-memory; `enable_external_access=false`; autoload/install extensions disabled; `memory_limit`, `threads`, `max_expression_depth`.
4. **Resource limits:** statement timeout (default 30s), result row cap (e.g., 10,000; UI paginates), and query concurrency cap per user.
5. **Process isolation:** SQL executes in a dedicated worker queue/process with no database credentials for application Postgres and no outbound network access.
6. **Server is authoritative:** client-side keyword checks in the UI (`DESIGN.md` §4.16) are UX only.
7. **Audit:** every executed query is stored (`sql_queries`: text, parameters, dataset version, user, duration, row count, status).

**AI-generated SQL** (P2) passes through the identical validator and sandbox; no special trust.

## 10.6 Caching (PRD §77)

- Cache keys always include `dataset_version_id` + `pipeline_version` + `config_hash` (e.g., `metrics:{run_key}:{metric_name}`), so a new version/config **cannot** hit stale entries.
- Redis caches: run progress, rendered chart data for hot dashboards, SQL result pages (short TTL), rate-limit counters.
- Persisted metrics in Postgres remain the source of truth; Redis is disposable and rebuildable.
- Cache invalidation is by key construction (versioned keys), not by explicit purge, wherever possible.

## 10.7 Data volume strategy (PRD §75–76, §119)

- Processing uses **Polars lazy scans over Parquet** (predicate/projection pushdown) to keep memory bounded.
- Profiling and EDA use single-pass aggregations; high-cardinality columns use approximate sketches only for **display hints**, never for reported metrics.
- Charts receive aggregated series (max ≈ 1,000 points) computed in the engine/DuckDB, with grain recorded in the chart spec.
- Tables paginate server-side with keyset pagination over a stable sort key.
- Configurable limits: `MAX_UPLOAD_BYTES`, `MAX_ROWS`, `MAX_COLUMNS`, worker memory limits. Exceeding limits fails fast at ingest with an explanatory error.

---

# 11. AI / LLM Architecture (PRD §53, §97)

## 11.1 Position in the system

```text
Analytics Engine ─► Verified Metrics ─► Rendered Insights ─► [LLM Gateway] ─► Explanations
                                                  ▲                │
                                                  └── number guard ┘
```

The LLM is **optional**; every feature must work (with plainer language) when it is disabled or unavailable.

## 11.2 Allowed uses (V1 and later)

| Use | Phase | Input to LLM | Output constraint |
|---|---|---|---|
| Ambiguous semantic-role suggestion | V1 | Column name, sample of non-sensitive values, stats | Must be one of the role enum; validated afterward |
| Natural-language explanation of insights | V1 | Insight record + metric IDs + values | May rephrase; may not introduce numbers |
| Executive summary text for reports | V1 | Verified metric/insight bundle | Same number guard |
| SQL assistance | P2 | Schema + question | Output goes through SQL validator/sandbox |
| Ask Your Data | V1.5 | Question + schema | Intent → SQL/calculation → execution → verified result → narration |

## 11.3 LLM gateway (`packages/llm_gateway`)

- Provider-agnostic interface (`complete(messages, schema?)`), pluggable adapters, timeouts, retries, circuit breaker, per-user/per-project rate limits, token and cost accounting, and request/response logging with **PII-safe redaction**.
- Prompts are versioned templates in the repo; the prompt version is stored with each generation (`AI_SPEC.md`).
- **Data minimization:** only aggregated metrics and minimal samples are sent; raw rows and personal identifiers are not sent by default. A per-project setting can disable all LLM usage.

## 11.4 Number-verification guard

For any generated text that will be shown to the user or placed in a report:

1. Extract all numeric tokens (including percentages, currency, dates where applicable).
2. Each must **match a provided metric value** (after the same display formatting) or be on an allow-list (e.g., ordinals, years in context).
3. Any unmatched number → reject the generation, retry once with a stricter instruction, then **fall back to the deterministic template text**.
4. Rejections are logged as quality signals.

This operationalizes PRD §51 ("never fabricate numbers") and §97.

## 11.5 Safety

- Prompt-injection hardening: dataset-derived strings (column names, values) are passed as quoted data in a separate delimited section; the system prompt states they are untrusted; outputs are schema-validated.
- LLM output is **never executed** (no code or SQL execution without the SQL validator).
- Generated text is labeled `AI-assisted` in the UI (`DESIGN.md` §10).

---

# 12. Authentication, Authorization, and Tenancy

## 12.1 Authentication (PRD §11–12)

- **Email/password:** Argon2id hashing with per-user salt and tuned parameters; password policy (length ≥ 10, breach-list check optional); constant-time compare; login throttling and progressive delays; generic error messages (no account enumeration).
- **Google OAuth:** Authorization Code + PKCE via Authlib; verify ID token (`iss`, `aud`, `exp`, `email_verified`); link by verified email with explicit conflict handling.
- **Sessions:** server-issued opaque session IDs in `HttpOnly; Secure; SameSite=Lax` cookies, stored server-side (Redis with Postgres fallback record) with idle (e.g., 30 min sliding) and absolute (e.g., 7 days) expiry; rotation on login/privilege change; logout invalidates server-side; "sign out everywhere" supported.
- **CSRF:** SameSite cookies + double-submit/anti-CSRF token on state-changing requests; Origin/Referer checks.
- **Password reset:** single-use, short-lived, hashed tokens; no token reuse; rate-limited.
- Expired session → `401` with code `SESSION_EXPIRED`; the UI shows the re-auth banner (`DESIGN.md` §5.2).

## 12.2 Authorization (PRD §67)

- **Ownership model:** every user-owned resource traces to `owner_id` (directly or via project). V1 has no sharing; roles beyond owner are reserved for later collaboration (P2).
- A single `authorize()` policy module is the only place access decisions are made; services call it before reads and writes. Row-scoped repositories provide a second layer.
- **Not found over forbidden:** unauthorized access to another user's resource returns `404` to avoid existence leakage.
- Object storage access: no public buckets; downloads use **short-lived presigned URLs** generated only after an authorization check; keys embed `owner_id` and are validated server-side against the caller.
- Worker tasks receive `owner_id` and verify resource ownership again before reading data (defense against forged/misrouted tasks).
- PostgreSQL Row-Level Security is a **P1 hardening option** documented in `SECURITY.md`; the application-layer scoping is mandatory regardless.

---

# 13. Security Architecture (PRD §82–83)

| Concern | Control |
|---|---|
| Transport | TLS everywhere; HSTS; secure cookies |
| Input validation | Pydantic models on every request; strict enums; size limits; filename sanitization (strip paths, normalize Unicode, random storage keys—user filenames never become storage paths) |
| File upload threats | Extension + magic-byte + MIME consistency; parser sandboxing with resource limits; XLSX: block external entity/zip bombs/macros (`.xlsm` rejected); JSON depth limits; CSV formula-injection neutralization on **exports** (prefix `'` for cells starting with `= + - @`) |
| SQL injection | ORM/parameterized queries for app DB; AST-validated, sandboxed analytical SQL (§10.5) |
| Authorization | Central policy + scoped repositories + 404-on-foreign (§12.2) |
| Secrets | Environment variables / secret manager only; never committed; startup validation fails fast if required secrets missing; secret scanning in CI (PRD §83) |
| Rate limiting | Redis token bucket per IP and per user on auth, upload, run-start, SQL, report endpoints |
| Error exposure | Global exception handler maps to coded errors; stack traces only in logs (with `request_id`) |
| Dependency risk | Lockfiles, `pip-audit`/`npm audit`/Dependabot, container image scanning, SBOM generation in CI |
| Headers | CSP (strict, nonce-based), `X-Content-Type-Options`, `Referrer-Policy`, `Frame-Options/frame-ancestors`, Permissions-Policy |
| Logging hygiene | No secrets, passwords, tokens, or raw dataset values in logs; PII redaction filter |
| Report/PDF generation | HTML templates auto-escaped; headless renderer runs with network disabled and no local-file access; user text sanitized |
| Multi-tenancy | Key-prefix isolation in storage, scoped queries, per-user quotas, no cross-tenant caches (cache keys include owner via run key) |
| Backups | PostgreSQL PITR + object-storage versioning for derived artifacts; raw datasets protected by object lock |
| Audit | Immutable `audit_events` for security- and data-relevant actions (§17) |

The complete threat model (STRIDE per container) and checklists live in `SECURITY.md`.

---

# 14. Reporting, Presentation, and Power BI Generation

## 14.1 Single source of truth (PRD §60, §96)

```text
Verified Metrics + Insights + Recommendations + Quality/Cleaning records
                              │
         ┌────────────────────┼───────────────────────┐
         ▼                    ▼                       ▼
   Report builder        Deck builder          Power BI builder
   (PDF / DOCX)            (PPTX)           (star schema + measures)
```

Generators **receive a read-only `ReportBundle`** assembled from persisted records (with metric IDs). They have no access to raw rows or the analytics engine's compute functions, which structurally prevents conflicting numbers.

## 14.2 Report builder

- Content model → templates: one canonical section model (Cover, Executive Summary, Dataset Overview, Data Quality, Data Preparation, EDA, SQL Analysis, Customers, Products, Sales, Insights, Recommendations, Limitations, Appendix — PRD §58).
- **PDF:** HTML/CSS templates rendered with WeasyPrint (or headless Chromium if layout needs demand; decision in `DECISIONS.md`). **DOCX:** `python-docx` using a styled template. Both are generated from the **same section model** to keep content identical.
- Charts are rendered server-side as static images (Matplotlib/Plotly+Kaleido) **from the chart specs and metric series**, using the `DESIGN.md` palette.
- **Limitations section** is assembled from deterministic checks (missingness, sample size, observational data, unavailable variables) — only relevant items are included (PRD §94).
- **Appendix** includes reproducibility metadata: dataset version & checksum, pipeline version, config hash, cleaning operations, SQL queries, metric definitions, generation timestamp (PRD §95).

## 14.3 Deck builder

- `python-pptx` with a master template; slide structure per PRD §59. Slide text is rendered from insights/metrics; each numeric element embeds the source metric ID in notes for traceability.
- Slides for unavailable modules are omitted or replaced with a clear "Not available — reason" slide, never filled with placeholders (PRD §126).

## 14.4 Power BI builder (PRD §55–57, §9.4)

- Output package (`powerbi/{run_id}.zip`):
  - `data/dim_customer.parquet|csv`, `dim_product`, `dim_date`, `dim_location`, `dim_payment`, `fact_sales` (surrogate keys, consistent grains).
  - `model/measures.dax` (Total Revenue, Total Orders, Total Quantity, Total Customers, AOV, Repeat Customer Rate, Revenue Growth, Revenue per Customer) — generated only for measures whose required fields exist.
  - `model/relationships.json` and `model/schema.md` (star schema documentation).
  - `spec/dashboard_spec.md|pdf`: five page specifications (PRD §57) with visuals, fields, and measures.
  - `README.md` — import steps for Power BI Desktop.
- Direct publishing to Power BI tenants is **explicitly out of scope** for V1; the architecture leaves an adapter seam (`PowerBIPublisher` protocol) for later.
- DAX measures are validated by a **reference-implementation test**: the same measure's definition is computed in Python on golden data and compared with the documented expectation (PRD §81).

## 14.5 Generation lifecycle

Requested via API → `generate` queue → status tracked like any job → artifact stored under `reports/…` → `reports` row created → notification + audit event. Downloads use presigned URLs and are audited (PRD §79).

---

# 15. Frontend Architecture (summary; details in `DESIGN.md`)

- **Next.js App Router** with a thin server layer acting as a BFF: forwards cookies to FastAPI, never holds business logic, never accesses the database.
- **Server state** via TanStack Query with typed client generated from OpenAPI; **form state** via React Hook Form + Zod; **UI state** local or minimal context (no global store unless justified).
- **Routing** per PRD §71; route-level `AsyncBoundary` implements Loading/Skeleton/Empty/Error/Processing/Partial/Retry (PRD §72).
- **Progress**: `useRunProgress(runId)` hook uses SSE with polling fallback; updates a normalized run cache so every tab reflects state without reloads.
- **Large data:** tables use server-side pagination + virtualization; charts consume pre-aggregated series; the browser never receives raw datasets (PRD §20, §75).
- **Formatting:** a single `lib/format` module (currency/percent/date/null) implements `DESIGN.md` §2.11; components never format inline.
- **Security:** no tokens in `localStorage`; CSP with nonces; strict `dangerouslySetInnerHTML` ban (lint rule); downloads via presigned URLs.
- **Accessibility and testing:** per `DESIGN.md` §9 and `TESTING.md`.

---

# 16. Deployment Architecture (PRD §84–86; details in `DEPLOYMENT.md`)

## 16.1 Local development (Docker Compose)

```text
services:
  web        (Next.js dev server)
  api        (FastAPI + uvicorn --reload)
  worker     (Celery: queues ingest, analysis, generate, light)
  postgres   (16)
  redis      (7)
  minio      (S3-compatible object storage)  # optional per PRD §84
  mailhog    (optional: password-reset emails)
```

One command (`make dev` / `docker compose up`) must start a fully working stack with seeded demo dataset and `.env.example` documenting all variables (PRD §83).

## 16.2 Production topology

```text
            ┌──────────── CDN / WAF ────────────┐
                           │
                   Load balancer (TLS)
              ┌────────────┴────────────┐
        Next.js (N replicas)       FastAPI (N replicas, stateless)
                                         │
        ┌────────────────┬───────────────┼───────────────┐
   PostgreSQL        Redis            Object storage   Celery workers
   (managed, HA,     (managed,        (S3-compatible,  (per-queue pools,
    PITR backups)     persistence)     versioned)       autoscaled)
```

- **Independent scaling** of web, API, and each worker pool (PRD §86, §120).
- **Stateless services**: no local disk state beyond temp; sessions in Redis; files in object storage.
- **Environments:** `dev`, `staging` (prod-like, synthetic data), `prod`. Config via environment variables; infra as code.
- **Migrations:** run as a pre-deploy job; backward-compatible (expand → migrate → contract) so rolling deploys are safe.
- **Health:** `/healthz` (liveness), `/readyz` (DB, Redis, storage reachability); worker heartbeat monitoring.
- **Zero-trust networking:** only the LB is public; Postgres/Redis/storage reachable from private network only; workers have egress limited to storage (and optionally LLM gateway); SQL-sandbox workers have no egress.

## 16.3 CI/CD

Pipeline: lint/type-check → unit tests → analytics golden tests → integration tests (containers) → build images → security scans → deploy to staging → E2E (Playwright) → manual/auto promote to prod. Releases tag the image with `git sha` and record `PIPELINE_VERSION`.

---

# 17. Observability and Auditability (PRD §78–79)

## 17.1 Logging

- Structured JSON logs with `request_id`, `user_id` (hashed where needed), `project_id`, `run_id`, `stage`, `dataset_version_id`, `pipeline_version`.
- Categories (PRD §78): application (auth, uploads, jobs, errors, report generation), worker (job/stage start/complete/fail, duration), analytics (dataset version, pipeline version, metrics generated, SQL executed).
- Correlation: the API assigns `request_id`; it is propagated into Celery task headers and back into logs and error payloads.

## 17.2 Metrics (Prometheus/OTel)

- API: request rate, latency (p50/p95/p99), error rate by `code`, auth failures.
- Workers: queue depth, task duration per stage, failure/retry rates, memory peak, run end-to-end time.
- Analytics quality: runs completed %, metrics per run, LLM guard rejection rate, SQL rejection rate.
- Storage/DB: pool saturation, slow queries, object-store error rates.

## 17.3 Tracing

OpenTelemetry spans across API → enqueue → worker stages → storage/DB, tagged with run and stage.

## 17.4 Alerts (examples)

Queue depth/age thresholds, failure-rate spikes, worker OOM kills, p95 latency regressions, storage errors, certificate expiry, backup failures.

## 17.5 Audit trail (PRD §79)

`audit_events` (append-only; no update/delete in application code):

```text
id, occurred_at, actor_user_id, action, resource_type, resource_id,
project_id, dataset_version_id?, run_id?, request_id, ip_hash, metadata(jsonb)
```

Recorded actions include: `dataset.uploaded`, `dataset.version.created`, `cleaning.operation.performed`, `analysis.started|completed|failed|cancelled`, `report.generated`, `report.downloaded`, `export.created`, `auth.login|logout|failed`, `project.deleted`, `mapping.changed`, `sql.executed`.

---

# 18. Error Handling Architecture (PRD §64–66)

## 18.1 Error taxonomy

| Class | Examples | User experience |
|---|---|---|
| Validation (client fixable) | invalid file, empty dataset, bad payload | Inline message with specific reason |
| Unavailable (data lacks prerequisites) | no customer ID for RFM | **Unavailable** state with reason + remedy (not an error) |
| Domain failure | cleaning rule conflict, SQL rejected | Error panel with plain language + Retry/Details |
| Transient infrastructure | storage timeout | Auto-retry; if exhausted, retryable failure |
| Authorization | foreign resource | 404/403 pages |
| Internal | unexpected exception | Generic message + `request_id`; details in logs only |

## 18.2 Mechanics

- Engine raises typed exceptions (`EngineError` subclasses with stable `code`, safe `user_message`, and `remedy`); infrastructure exceptions are wrapped, never leaked.
- API global handler converts to the error envelope (§7.2); workers persist `error_code`, `user_message`, `remedy`, and an internal `diagnostic_ref` (log correlation) on `stage_runs`.
- **Unavailable ≠ Failed:** modules resolved as unavailable are first-class results stored as `module_availability` records (`module`, `state`, `reason`, `required_roles`) and drive the UI availability banners (PRD §66).
- Partial success is persisted explicitly: a run can be `COMPLETED` with some modules `Unavailable`.

---

# 19. Performance Architecture (PRD §75, §119)

| Concern | Strategy |
|---|---|
| Page load | Next.js SSR for shell; code-splitting per route; lazy-load chart libs; cache-friendly static assets via CDN |
| API latency | Persisted, precomputed metrics/series served from Postgres; indexed queries; pagination everywhere; response compression |
| Large datasets | Parquet + Polars lazy scans; single-pass aggregations; streaming ingest; memory caps per task |
| Charts | Server-side aggregation (≤ ~1,000 points/series); sampling with deterministic seed for scatter, disclosed in subtitle |
| Tables | Keyset pagination, server-side sort/filter on indexed or Parquet-pushdown columns; DOM virtualization |
| SQL queries | DuckDB vectorized execution; row/time limits; result paging |
| Background work | Queue separation; per-user concurrency limits; backpressure via queue length checks returning `429`/"queued" status |
| Caching | Version-keyed Redis caches (§10.6); HTTP caching headers for immutable artifacts |
| DB | Connection pooling, prepared statements, targeted indexes, query review in CI (EXPLAIN checks for hot paths) |

Initial targets (to be validated and tuned during implementation, PRD §119): API p95 < 300 ms for non-compute endpoints; first meaningful page render < 2.5 s on broadband; a 100k-row retail dataset completes the core analysis pipeline in minutes, with progress visible throughout.

---

# 20. Testing Architecture (PRD §80–81; details in `TESTING.md`)

| Level | Scope | Tools |
|---|---|---|
| **Analytics golden tests** | Deterministic datasets with hand-verified expected metrics (e.g., Customer A ₹100+₹200, B ₹300 → total ₹600) run through the **full engine**; tests fail on any deviation | pytest; fixtures in `packages/analytics_engine/tests/golden/` |
| **Property-based tests** | Invariants: cleaning never increases rows; revenue by category sums to total; RFM scores within bounds; segment counts sum to customers; idempotent re-run yields identical outputs | hypothesis |
| **Unit tests** | Profiling, type/semantic detection, quality scoring, cleaning ops, segmentation, RFM, SQL validation, insight templates, number guard | pytest |
| **SQL safety tests** | Corpus of malicious/edge queries (stacked statements, comments, `read_csv`, `ATTACH`, unicode tricks) must all be rejected | pytest |
| **Integration tests** | API ↔ Postgres ↔ Redis ↔ MinIO ↔ Celery with real containers; authorization matrix (user A cannot access user B on every endpoint) | testcontainers, pytest |
| **Contract tests** | OpenAPI schema snapshot; frontend client regeneration check | schemathesis / snapshot |
| **E2E** | Login → create project → upload → process → view analysis → generate report (+ Google OAuth with a mock IdP) | Playwright |
| **Frontend** | Component tests, a11y (axe), visual regression of key states | Vitest, Testing Library, Storybook, Playwright |
| **Non-functional** | Load test of upload + pipeline on large synthetic datasets; worker OOM/chaos tests (kill during stage → resume) | k6/Locust |
| **Reproducibility test** | Run the same dataset version + config twice (and across worker restarts): all metric values byte-identical | pytest |
| **Report consistency test** | Every number in PDF/DOCX/PPTX text maps to a persisted metric | pytest + parser |

**CI gates:** a failing golden or reproducibility test blocks merge. Coverage targets are enforced for `analytics_engine` (high, e.g., ≥ 90% line/branch on core modules) and security-critical code.

---

# 21. Data Governance, Privacy, and Retention (PRD §67, §110)

- **Privacy by default:** all data private to the owner; no cross-tenant aggregation; no use of customer data for model training. LLM usage is opt-out per project and minimizes data sent (§11.3).
- **Retention policy (configurable):**

| Data | Default | Behavior |
|---|---|---|
| Uploaded raw datasets | Until user deletes project/dataset | Permanent deletion queued after soft-delete grace period |
| Cleaned versions / derived tables | Tied to dataset lifetime | Deleted with dataset |
| Generated reports/decks/exports | Configurable (e.g., 90 days) | Lifecycle rule; regenerable from runs |
| Temp files | 24 hours | Object-store lifecycle rule |
| Failed-job artifacts | 7 days | Cleanup task |
| Audit events | Longer retention (e.g., 1 year) | Metadata only; no dataset content |

- **Deletion semantics (PRD §108–109):** projects are **soft-deleted** first (recoverable window), then permanently purged by a retention job that removes DB rows and object-store keys; dataset deletion is blocked/flagged when dependent runs/reports exist, with explicit cascade confirmation.
- **Data export / account deletion:** users can export their data and delete their account; deletion removes owned objects and anonymizes retained audit references.
- **PII awareness:** the profiler flags likely PII columns (names, emails, phone numbers); these are excluded from LLM prompts and log output, and may be masked in previews if configured.

---

# 22. Architecture Decision Records (seed list for `DECISIONS.md`)

| ID | Decision | Status |
|---|---|---|
| ADR-001 | Modular monolith + separate worker process for V1 | Accepted |
| ADR-002 | Pure-Python analytics engine package with no framework imports | Accepted |
| ADR-003 | Polars as primary dataframe engine (pandas only for compatibility) | Accepted |
| ADR-004 | Parquet as the canonical dataset storage format | Accepted |
| ADR-005 | DuckDB sandbox for analytical SQL (not application Postgres) | Accepted |
| ADR-006 | Immutable, hash-verified dataset versions with lineage | Accepted |
| ADR-007 | Metric registry; persisted metric records are the sole numeric source for downstream consumers | Accepted |
| ADR-008 | LLM gateway with number-verification guard and deterministic fallback | Accepted |
| ADR-009 | Server-side sessions in httpOnly cookies; Argon2id | Accepted |
| ADR-010 | Direct-to-object-storage uploads via presigned multipart | Accepted |
| ADR-011 | SSE for progress with polling fallback | Accepted |
| ADR-012 | Run-key idempotency (`dataset_version + config + pipeline_version + mapping`) | Accepted |
| ADR-013 | Chart library selection (Recharts vs ECharts) | **Open** — decide before Milestone 3 |
| ADR-014 | PDF engine (WeasyPrint vs headless Chromium) | **Open** — decide before Milestone 6 |
| ADR-015 | Postgres Row-Level Security as additional tenancy layer | **Open** — evaluate in Milestone 7 |
| ADR-016 | Monetary aggregation precision (float64 vs Decimal) | **Open** — decide with `ANALYTICS_SPEC.md` |

Each ADR records context, options, decision, consequences, and date. Open ADRs must be closed before the milestone that depends on them.

---

# 23. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Heuristic semantic detection mislabels columns | Wrong analytics | Validation step, confidence display, mandatory user-visible mapping with override, golden tests across messy headers |
| Large file memory pressure | Worker OOM, failed runs | Streaming ingest, Polars lazy scans, per-task memory limits, configurable caps, chaos tests |
| SQL sandbox escape | Cross-tenant data exposure | Layered controls (§10.5), isolated process/network, curated allow-list, adversarial test corpus, security review |
| LLM hallucinated numbers | Loss of trust (core principle) | Number guard + deterministic fallback + LLM optional |
| Metric drift between report and dashboard | Contradictory numbers | Single metric store, `ReportBundle` read-only contract, report consistency test |
| Pipeline changes silently alter historical results | Reproducibility loss | `PIPELINE_VERSION` bump rule, runs pinned to version, golden snapshot diffs in CI |
| Scope creep toward "any dataset" | Unreliable V1 | Domain plugin boundary; retail-only in V1; unsupported paths explain limitation (PRD §9.1, §116) |
| Long-running jobs stall queues | Poor UX | Queue separation, time limits, concurrency limits, backpressure |
| Misleading charts / causal language | Incorrect decisions | Chart rules in `DESIGN.md`, template linter blocking causal verbs, Association labeling |
| Currency/locale assumptions | Wrong displays | Currency as metadata; formatting only at presentation layer (PRD §112, §114) |

---

# 24. Implementation Guidance

## 24.1 Build order (aligned with PRD §129)

1. **M1 Foundation:** monorepo, CI, Docker Compose, Postgres + Alembic, auth (email/password + Google), session handling, shared error envelope, app shell.
2. **M2 Dataset:** projects, presigned upload, ingest worker, validation, Parquet v1, preview endpoints, metadata.
3. **M3 Analytics:** profiling, semantic detection, quality scoring, cleaning + versioning, EDA, stage/job framework, SSE progress.
4. **M4 Business analytics:** metric registry, DuckDB sandbox, SQL explorer, retail modules, segmentation, RFM, insights/recommendations (with evidence drawer data).
5. **M5 BI:** star schema export, DAX measures, dashboard spec, Power BI package.
6. **M6 Reporting:** report/deck builders, LLM gateway + guard (if enabled), downloads, notifications.
7. **M7 Production:** security hardening, observability dashboards/alerts, load tests, retention jobs, deployment automation.

## 24.2 Definition of Done for architectural components

A component is done only when (PRD §125): implemented across layers, validated, error-handled with coded errors, tested (including golden/property tests where numbers are involved), documented in the relevant spec, instrumented (logs/metrics/traces), and covered by authorization tests.

## 24.3 Non-negotiable rules (summary)

1. Raw data is write-once; every change creates a new version.
2. Only the analytics engine produces numbers; everything else references metric IDs.
3. Analytical SQL runs only in the sandbox, validated at the AST level.
4. Every owned-resource access passes through the central authorization layer and scoped repositories.
5. Long-running work never runs in a request/response cycle.
6. Runs are idempotent, versioned, and reproducible.
7. LLM output never introduces numbers and never executes.
8. No stack traces, secrets, or raw data in logs or error responses.
9. Unavailable ≠ failed: missing prerequisites produce explained, first-class "unavailable" results.
10. No architectural change without a `DECISIONS.md` entry.

---

# 25. Traceability to PRD

| PRD Section | Architecture Section |
|---|---|
| §5 Principles | §1, §8.1, §11, §24.3 |
| §10 Workflow | §8.3, §10.2 |
| §11–12 Authentication | §12.1 |
| §17–20 Upload/validation/preview | §10.2, §13 |
| §21–26 Profiling/quality/duplicates | §8.2, §8.6 |
| §27–30 Cleaning/versioning | §8.6, §10.3 |
| §31–35 EDA | §8.2, §19 |
| §36–45 Retail analytics | §8.8 |
| §46–48 SQL & safety | §10.5 |
| §49–52 Metrics/insights/recommendations | §8.4, §8.9 |
| §53–54 AI / Ask Your Data | §11 |
| §55–57 Power BI | §14.4 |
| §58–60 Reports & presentation | §14 |
| §61–66 Status/progress/errors/partial | §7.4, §9, §18 |
| §63 Background processing | §9 |
| §67–69 Privacy, storage, DB | §10.1, §10.4, §12.2, §21 |
| §70–74 Frontend | §15 |
| §75–77, §119 Performance/caching | §10.6, §10.7, §19 |
| §78–79 Observability/audit | §17 |
| §80–81 Testing | §20 |
| §82–83 Security/env | §13 |
| §84–86 Docker/architecture | §16 |
| §87–89 API principles | §7.2 |
| §95–97 Reproducibility/source of truth/AI | §8.4, §9.5, §10.3, §11 |
| §103–104 Retry/idempotency | §9.4, §9.5 |
| §108–110 Deletion/retention | §21 |
| §112–114 Currency/dates/precision | §8.1, §14.2 |
| §121–123 Extensibility/domains | §8.7, §8.8 |
| §126 Prohibited shortcuts | §24.3, §22 |
