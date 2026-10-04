# InsightForge — Implementation Plan (IMPLEMENTATION_PLAN.md)

**Version:** 1.0
**Status:** Authoritative for development *order*. Where this plan and a specification disagree on behavior, the specification wins and the disagreement is logged in `DECISIONS.md` (PRD §127).
**Depends on:** `PRD.md` (§124–129), `ARCHITECTURE.md` (§6, §24), `DATABASE.md` (§14 grants, §15 migration policy and order), `API_SPEC.md`, `SQL_SPEC.md`, `POWERBI_SPEC.md`, `ANALYTICS_SPEC.md` (partially written — see §2.3), `DESIGN.md`
**Audience:** the developer driving the build, and the coding agents (Google Antigravity) executing work packages
**Builds from:** the existing prototype (static HTML workspace + pure-Python engine + FastAPI/DuckDB server on port 8080)

---

# 1. Strategy in One Page

1. **Treat the prototype as a spike, not a foundation.** It proved the product story (10-stage pipeline, evidence drawer, RFM, star schema). It does not meet several non-negotiable rules (§2.2). Freeze it as a reference and build the production system in the monorepo from `ARCHITECTURE.md` §6. Reuse ideas, fixtures, and visual design — not the code structure.
2. **Close the specification first, but only what blocks the next step.** Phase 0 resolves the cross-document conflicts and finishes `ANALYTICS_SPEC.md`. Foundation work does not wait for it; engine work does.
3. **Correctness before screens.** The pure-Python engine, golden datasets, and property tests come before any page that displays a number. A number shown without a verified metric behind it violates PRD §126.
4. **Contract first, vertical slices second.** Each slice is: migration → repository → engine/worker → API → generated client → UI page → E2E test, shipped together (PRD §125 Definition of Done).
5. **Three lanes in parallel, one lane owns each shared file.** Platform (DB/API/workers), Engine (pure Python), Web (Next.js). Migrations and `shared_schemas` have a single writer at a time.
6. **Every work package ends at a gate.** `make gate` must be green, a spec-conformance checklist must be ticked, and a reviewable artifact (test report, walkthrough) must exist before the next package starts.
7. **Order follows PRD §129 / ARCHITECTURE §24.1** (M1 Foundation → M2 Dataset → M3 Analytics → M4 Business Analytics → M5 BI → M6 Reporting → M7 Production), with Phase 0 in front and the engine lane running ahead of the platform lane.

```text
Phase 0  Spec closure + prototype triage ─────────────────────────────┐ (blocks only the WPs that name it)
Phase 1  Foundation (M1)            Lane A+C ───────────────┐          │
Phase 2  Engine core I              Lane B ─────────────────┼──┐       │
Phase 3  Datasets & ingestion (M2) ─────────────────────────┘  │ needs 1 + 2
Phase 4  Runs, quality, cleaning, EDA (M3)                      │
Phase 5  SQL sandbox + metric registry (M4a)                    │
Phase 6  Retail analytics + insights (M4b)                      │
Phase 7  Power BI package (M5)                                  │
Phase 8  Reporting: PDF · DOCX · PPTX (M6)                      │
Phase 9  Production hardening + release (M7) ◄──────────────────┘
```

**Indicative effort** (planning heuristic, not a commitment): ≈ 85 work packages; with one developer supervising agents in two to three parallel lanes, **16–24 weeks**; with two developers, **10–14 weeks**. Size legend used below: **S** ≤ ½ day · **M** 1–2 days · **L** 3–5 days · anything larger must be split before starting.

---

# 2. Where You Are Today

## 2.1 What the prototype demonstrates (from your inventory)

A landing page with a Three.js factory, an auth page, a 12-tab workspace, a standalone analytics package covering ingestion → quality → cleaning → mapping → EDA → RFM → products → SQL → star schema → insights → pipeline, and a FastAPI server on port 8080 backed by in-memory DuckDB. I have not seen the code, only your description, so Phase 0 verifies the points below rather than assuming them.

## 2.2 Conflicts between the prototype and the specifications

| # | Prototype behavior (as described) | Rule it conflicts with | Consequence |
|---|---|---|---|
| 1 | "Enter Workspace Directly (Demo Analyst)" bypass button, pre-filled credentials | PRD §126: *must not bypass authentication* | Remove. Replace with a seeded **real** dev account that logs in through the real flow (WP-1.12) |
| 2 | Workspace UI shows concrete figures (87/100 quality, 91.4 % completeness, 12-month trend, 6 insights) | PRD §126: *no static dashboard numbers, no fake API responses* | Verify every figure is fetched from the API (WP-0.2). Anything literal in HTML is deleted during the rewrite |
| 3 | Server keeps a single global "active dataset" in memory | ARCHITECTURE §24.3 (ownership scoping, immutable versions); DATABASE tenancy model | Replace with projects → datasets → versions → runs in PostgreSQL, owner-scoped (Phases 3–4) |
| 4 | Static HTML hosted by FastAPI | ARCHITECTURE §6/§21: Next.js + BFF, httpOnly cookie sessions | Rebuild the UI in `apps/web`; keep the visual language |
| 5 | Engine modules are flat files; `types.py` holds Pydantic schemas | ADR-002 (engine imports only `shared_schemas`); ARCHITECTURE §6 layout | Restructure into `insightforge_engine/{ingest,profiling,…}` and move shared contracts to `shared_schemas` |
| 6 | Cleaner imputes missing values (median/mode) as a standard step | ANALYTICS_SPEC P5 / PRD §26–35: flag by default, never silently impute metric columns | Default becomes *flag only*; imputation is an explicit, logged, non-money operation |
| 7 | Quality profiler computes four dimensions with its own formulas | ANALYTICS_SPEC §8 (exact weights, sensitivities, components) | Re-implement against the spec; keep the prototype's numbers only as a comparison fixture |
| 8 | Role names such as `TRANSACTION_DATE` | DATABASE `semantic_role` enum uses `PURCHASE_DATE` | Rename to the enum; one source of enum values (WP-1.4) |
| 9 | RFM scores by "rank cutoffs" | SQL_SPEC §5.7 uses `NTILE` with ID tie-break — **both** treat tied customers unequally (see D-01) | Decide scoring in Phase 0, implement once in SQL, reuse in Power BI and reports |
| 10 | SQL sandbox *denies* mutation keywords via SQLGlot; table aliases `retail_sales`, `sales` accepted | SQL_SPEC §4, §7: **allow-list** relations/functions, canonical SQL, engine-level lockdown, resource limits | Rebuild per spec; remove extra aliases (they widen the allow-list) |
| 11 | Star schema JSON with `dim_dates`, `dim_customers`, `dim_products`, `dim_payment_methods`; 10 DAX measures; JSON download | POWERBI_SPEC §4–§7: `dim_date`, `dim_customer`, `dim_product`, `dim_payment`, `dim_location`, `dim_discount_band`; ZIP with CSV, M queries, manifest, reference values | Rebuild the builder; the ERD visual can be reused |
| 12 | Reports: Markdown works; PDF/DOCX/PPTX appear as generator cards | PRD §124: PDF, DOCX, PPTX must really generate | Verify in WP-0.2; real generators land in Phase 8 |
| 13 | Python 3.14, DuckDB 1.5.x | Reproducibility needs pinned, tested versions (ANALYTICS_SPEC §3.5) | Run a wheel-availability and conformance check in WP-1.1; drop to the newest minor all dependencies support if anything is missing |

## 2.3 State of the specification set

| Document | State |
|---|---|
| `PRD`, `DESIGN`, `ARCHITECTURE`, `DATABASE`, `API_SPEC`, `SQL_SPEC`, `POWERBI_SPEC` | Complete |
| `ANALYTICS_SPEC` | **Sections 1–8 written** (principles, execution model, numeric policy, ingest, profiling, semantic detection, data quality). Sections 9–25 (cleaning, transform, EDA, retail definitions, segmentation/RFM/loyalty, metric registry, insight engine, availability, SQL/Power BI/report contracts, errors, limits, tests, config, decisions) are **not yet written**, and sections 1–10 need the revisions in Appendix G after reading `SQL_SPEC` and `POWERBI_SPEC` |
| `TESTING`, `SECURITY`, `REPORTING_SPEC`, `AI_SPEC`, `DEPLOYMENT`, `DECISIONS` | Not written. Each is scheduled **just before the first work package that needs it** (§5 and Appendix F) |

## 2.4 Reuse matrix (what to keep)

| Prototype asset | Verdict | Where it goes |
|---|---|---|
| CSS design tokens, dark theme, typography choices | **Keep** | `apps/web` Tailwind theme, from `DESIGN.md` §2 (verify values against the doc, not the prototype) |
| Evidence-drawer UX, 10-stage stepper, RFM heat grid, star-schema ERD visual | **Keep as visual reference** | Rebuilt as typed React components (WP-1.11, 4.6, 5.8, 6.3, 7.5) |
| Three.js factory landing page | **Defer** | Port last, optional (WP-9.9) |
| `sample_data.py` (10 k synthetic transactions) | **Keep as fixture** | Golden dataset G8, with a fixed seed (WP-2.2) |
| `ingestion.py` encoding/delimiter sniffing logic | **Refactor** | `ingest/` readers (WP-2.3); text-first typing replaces auto-inference |
| `eda.py` statistics functions | **Refactor** | `eda/` + `stats/`, verified against ANALYTICS_SPEC §6/§11 definitions (WP-2.8) |
| `quality.py`, `cleaner.py`, `schema_mapper.py`, `rfm.py`, `product_analytics.py`, `sql_sandbox.py`, `star_schema.py`, `insights.py`, `pipeline.py` | **Rewrite against the specs**, using the prototype only as an independent reference to cross-check results | See Appendix A |
| `server.py` | **Discard** | Replaced by `apps/api` + workers |
| `workspace.html`, `auth.html`, `index.html` | **Archive** | `prototype/` folder, read-only |

---

# 3. Operating Model with Google Antigravity

> Antigravity's configuration surfaces have been changing (Agent Manager, rules, workflows, skills, and a CLI successor). The locations below were current when this plan was written; confirm them in your installed version before WP-1.2.

## 3.1 Principles

1. **Specs are the source of truth, not the agent's memory.** All documents live in `docs/`. Agents read **slices** (§8), never whole documents — the specification set is far larger than a useful context window.
2. **One work package = one agent conversation = one branch = one pull request.** Fresh context per package; the package prompt names its spec slices and its gate.
3. **Plan first for anything M or larger.** Use Planning mode; require the implementation-plan artifact and approve it before code is written. Use Fast mode only for S packages and UI polish.
4. **The agent may not invent behavior.** If a spec is silent or contradictory, the agent writes a proposal into `docs/DECISIONS.md` and stops (§3.6 rule 3).
5. **Tests are written from the spec before the implementation** for every package that produces numbers (golden fixtures, property tests, safety corpus).
6. **Machines check conformance, not agents.** `make gate` runs lint, types, tests, import boundaries, migration round-trip, and API-inventory checks. An agent reporting "done" without a green gate is not done.

## 3.2 Repository configuration to create (WP-1.2)

```text
GEMINI.md                      # project constitution (loaded every task) — template in Appendix B
AGENTS.md                      # same content; keeps other tools in sync
.agent/
├── rules/
│   ├── 00-constitution.md     # non-negotiables (PRD §126, ARCHITECTURE §24.3)
│   ├── 10-engine.md           # determinism, decimals, ordering, no framework imports
│   ├── 20-api-db.md           # envelope, authz, migrations, idempotency
│   ├── 30-web.md              # tokens only, 8 UI states, a11y, no literal numbers
│   ├── 40-testing.md          # golden/property/safety/e2e expectations
│   └── 50-security.md         # secrets, logging, uploads, SQL sandbox
├── workflows/                 # slash-invoked saved prompts — Appendix D
│   ├── start-wp.md   finish-wp.md   spec-check.md   new-migration.md
│   ├── new-endpoint.md   new-metric.md   golden-update.md   audit-shortcuts.md
└── skills/                    # optional: sql-template-author, dax-measure-author
docs/                          # PRD, DESIGN, ARCHITECTURE, DATABASE, API_SPEC, SQL_SPEC, POWERBI_SPEC,
                               # ANALYTICS_SPEC, DECISIONS, SPEC_INDEX, api_inventory.yaml
```

`docs/SPEC_INDEX.md` is a generated table of contents (heading → line range) per document so an agent can open exactly the lines a package names.

## 3.3 Agent settings

| Setting | Value | Why |
|---|---|---|
| Mode | Planning for M/L; Fast for S | Large packages need a plan artifact you can review |
| Review policy | **Always ask** for migrations, auth, sessions, sandbox, security, deploy; **agent decides** for UI polish and docs | Keep human review where mistakes are expensive |
| Terminal allow-list | `make *`, `uv run pytest …`, `uv run ruff …`, `pnpm test\|lint\|build`, `alembic upgrade\|downgrade`, `docker compose up\|logs` | Predictable, non-destructive |
| Terminal deny / always-ask | `rm -rf`, `git push --force`, `git reset --hard`, `docker system prune`, any `DROP`/`TRUNCATE`, writing outside the workspace | Prevent irreversible damage |
| Browser agent | Allowed against `localhost` only; used for visual verification and walkthrough recordings | Real regression tests are Playwright code, not agent clicks |
| Secrets | `.env` is git-ignored; agents see `.env.example` only | PRD §126: no secrets in source |

## 3.4 Required artifacts per work package

| Package size | Before coding | At the end |
|---|---|---|
| S | One-paragraph plan in chat | `make gate` output |
| M | Implementation-plan artifact approved by you | `make gate` output + spec-conformance checklist |
| L | Plan artifact **plus** list of files to be created and tests to be written first | Test report, walkthrough (screenshots/recording for UI), checklist, and a short note of anything deferred |

## 3.5 Parallel work (Manager view)

| Lane | Owns | May run concurrently with |
|---|---|---|
| **A — Platform** | `apps/api`, `workers/`, `apps/api/.../db` (migrations), `infra/` | B, C |
| **B — Engine** | `packages/analytics_engine`, golden fixtures | A, C |
| **C — Web** | `apps/web` | A, B (against the OpenAPI contract and mocked-at-the-edge fixtures **in tests only**, never in the running product) |
| **D — Docs/Quality** | `docs/`, `TESTING.md`, CI | any |

Rules: at most **three** agents at once; **migrations and `packages/shared_schemas` are single-writer** (one agent at a time); two agents never edit the same package; a package that consumes another lane's output starts only after that output's gate is green (dependencies column in §5).

## 3.6 Stop-the-line rules (copy into `00-constitution.md`)

1. Never hardcode a number, insight, or API response that the product displays. Fixtures live under `tests/` only.
2. Never bypass authentication or authorization, in code or in a "demo" path.
3. If a spec is silent, contradictory, or the agent wants to deviate: **stop**, write a proposal in `DECISIONS.md`, and wait for approval.
4. Never run or build unrestricted SQL; SQL goes only through the validator and sandbox.
5. Never mutate a dataset version; every change creates a new version and a log entry.
6. Never add a dependency without a one-line justification in the PR description (PRD §126).
7. If `make gate` is red, fix it or stop; never disable, skip, or loosen a test to make it pass.
8. If a golden snapshot changes, the PR must say why and bump the relevant version (`PIPELINE_VERSION`, `template.version`, `model_version`).

---

# 4. Global Engineering Gates

## 4.1 `make gate` (the single definition of "green")

| Step | Tooling | Applies from |
|---|---|---|
| Format + lint | `ruff` (Python), `eslint` + `prettier` (web) | WP-1.1 |
| Static types | `mypy --strict` or `pyright` (engine and API), `tsc --noEmit` strict | WP-1.1 |
| Import boundaries | `import-linter` encoding ARCHITECTURE §6 dependency rules | WP-1.1 |
| Unit + property tests | `pytest` + `hypothesis` | WP-1.1 |
| Golden analytics tests | `pytest -m golden` against `tests/golden/` | WP-2.2 |
| Migration round-trip | `alembic upgrade head` → `downgrade base` → `upgrade head` on a throwaway Postgres | WP-1.5 |
| API inventory | `scripts/spec_inventory.py` compares the generated OpenAPI with `docs/api_inventory.yaml` (every endpoint tagged with the phase that owns it; endpoints due this phase must exist, undocumented endpoints fail) | WP-1.6 |
| Contract tests | schema-based API tests from the OpenAPI document (`schemathesis`) | WP-3.7 |
| Web unit + a11y | `vitest`, `@testing-library/react`, `axe` checks per component | WP-1.11 |
| E2E | `playwright` against `docker compose -f infra/compose/docker-compose.test.yml` | WP-3.9 |
| Security gates | dependency audit, secret scan, SAST; SQL safety corpus (from WP-5.1) | WP-1.3 / WP-5.1 |

Dependencies introduced by this plan (each needs the one-line PR justification): `uv`, `ruff`, `mypy`/`pyright`, `pytest`, `hypothesis`, `import-linter`, `schemathesis`, `playwright`, `axe`. All are test/dev tooling, none ship in the runtime image.

## 4.2 Definition of Done (PRD §125, applied to every package)

A package is done only when all of these hold where applicable: frontend + backend + database + validation + error handling + tests + documentation are implemented; authorization tests exist for every new owned resource; every new error uses a coded error from the catalog; every new metric/template/measure has a golden test; the relevant spec section is updated if behavior changed; logs/metrics are emitted without leaking data.

## 4.3 Test pyramid by phase

| Phase | Dominant tests |
|---|---|
| 1 Foundation | Unit, authz matrix, migration round-trip, component + a11y |
| 2 Engine | Unit, **golden**, **property** (INV-01…12), determinism (thread-count 1 vs N) |
| 3–4 Datasets, runs | Integration (compose), contract, E2E upload→run, reproducibility across worker restart, SSE resume |
| 5 SQL | **Adversarial safety corpus**, sandbox conformance, template lint, metric parity vs independent Polars reference |
| 6 Analytics | Property invariants across modules, partial-analysis matrix (missing roles), snapshot regression, insight-language linter |
| 7 BI | DAX/M lint (L0), Python reference evaluator (L1), determinism of ZIP, PII modes; L2 scheduled |
| 8 Reporting | Report-consistency (every number resolves to a metric), number-guard tests, file validity (open/parse PDF/DOCX/PPTX) |
| 9 Production | Load, chaos (OOM/queue stall), security review, a11y audit, full-journey E2E |

## 4.4 Branch, commit, and release policy

- Trunk-based: short-lived branch per package `wp/<id>-<slug>`; squash-merge after green gate and your review.
- Conventional commits; one changelog line per package in `docs/CHANGELOG.md`.
- Tags at each milestone gate: `m1-foundation` … `m7-production`.
- `PIPELINE_VERSION` starts at `1.0.0` and follows ANALYTICS_SPEC §3.7; any golden-snapshot diff requires a justified bump.

---

# 5. THE ORDER — Master Sequence

Read top to bottom. A package may start only when everything in **Needs** has passed its gate. **Lane**: A = Platform, B = Engine, C = Web, D = Docs/Quality. Packages in the same phase with disjoint lanes and satisfied dependencies run in parallel.

## Phase 0 — Specification closure and prototype triage (no production code)

| ID | Work package | Size | Needs | Lane |
|---|---|---|---|---|
| WP-0.1 | Tag the prototype (`prototype-v0`), move it to `prototype/`, mark read-only | S | — | D |
| WP-0.2 | Prototype audit → `docs/PROTOTYPE_AUDIT.md` (hardcoded numbers, auth bypass, global state, dependency list, Python/DuckDB versions) | M | 0.1 | D |
| WP-0.3 | Cross-document reconciliation → `docs/DECISIONS.md` (decision backlog in §10) | M | 0.2 | D |
| WP-0.4 | Finish `ANALYTICS_SPEC.md`: revise §1–10 (Appendix G), write §9–25 | L | 0.3 | D |
| WP-0.5 | `TESTING.md` + golden-dataset catalog (G1–G8) + invariant list | M | 0.4 (needs §22 draft) | D |
| WP-0.6 | `SECURITY.md` (sessions, CSRF, rate limits, upload safety, sandbox isolation, secrets, logging, tenancy, SQL-worker persistence path) | M | 0.3 | D |

**Gate G0:** `DECISIONS.md` has an accepted answer for every decision marked "needed by ≤ Phase 2"; `ANALYTICS_SPEC.md` §1–10 are consistent with `SQL_SPEC.md`; prototype audit reviewed. Phase 1 may start after WP-0.1 and WP-0.2; engine WPs wait for the parts of WP-0.4 they name.

## Phase 1 — Foundation (PRD Milestone 1)

| ID | Work package | Size | Needs | Lane |
|---|---|---|---|---|
| WP-1.1 | Monorepo skeleton (ARCHITECTURE §6), `uv` + `pnpm` workspaces, ruff/mypy/pytest/hypothesis, eslint/prettier/tsc, `import-linter` boundaries, Python-version compatibility check | M | 0.1 | A |
| WP-1.2 | Antigravity configuration: `GEMINI.md`, `.agent/rules`, `.agent/workflows`, `docs/SPEC_INDEX.md`, `docs/api_inventory.yaml` skeleton | S | 1.1 | D |
| WP-1.3 | Docker Compose (Postgres 16, Redis, MinIO, mail catcher), env/config contract, secret scan, CI pipeline running `make gate` | M | 1.1 | A |
| WP-1.4 | `shared_schemas`: error envelope, pagination, id types, **enums generated from one source** (DATABASE §4) and exported to TypeScript | M | 1.1, 0.3 | A |
| WP-1.5 | DB baseline: Alembic, `0001_extensions_and_functions`, `0002_identity` **with `audit_events`** (D-13), role/grant harness, migration round-trip test | L | 1.3, 1.4 | A |
| WP-1.6 | API core: app factory, config, request IDs, structured logging, error handlers + closed error catalog, health/readiness, OpenAPI export, API-inventory check | M | 1.4, 1.5 | A |
| WP-1.7 | Auth: register, login, logout, sessions (httpOnly cookie), Argon2id, CSRF, rate limiting, audit events | L | 1.6, 0.6 | A |
| WP-1.8 | Google OAuth (PKCE) + password reset (mail catcher in dev) | M | 1.7 | A |
| WP-1.9 | Authorization layer + scoped repositories + reusable **cross-tenant test fixture** ("user B gets 404") | M | 1.7 | A |
| WP-1.10 | Web shell: Next.js App Router, Tailwind tokens from DESIGN §2, fonts, BFF cookie proxy, generated typed API client, app shell (sidebar, top bar, command-palette skeleton) | L | 1.6, 1.4 | C |
| WP-1.11 | Design-system primitives (Button, Input, Card, Badge, Tabs, Table, Drawer shell, Toast, Skeleton, EmptyState, ErrorState, the **8 UI states** pattern) + axe harness | L | 1.10 | C |
| WP-1.12 | Auth UI (sign in / create account / forgot / reset / Google), route guards, `make seed-dev` real dev account — **no bypass** | M | 1.8, 1.11 | C |

**Gate G-M1 (tag `m1-foundation`):** register, login, Google login, logout work end to end; cross-tenant matrix green; `docker compose up` + `make gate` green in CI; app shell renders with real session; no literal numbers anywhere in `apps/web`.

## Phase 2 — Engine core I (pure Python; runs in Lane B alongside Phase 1)

| ID | Work package | Size | Needs | Lane |
|---|---|---|---|---|
| WP-2.1 | Engine skeleton (`insightforge_engine/` layout), `common/` (canonical JSON, hashing, decimal helpers, seeds, display formatting), `version.py`, `RunContext`, `Stage` protocol | M | 1.1, 0.4 (§3–4) | B |
| WP-2.2 | Golden fixtures G1–G8 with hand-verified expected values; `-m golden` marker and snapshot tooling | L | 0.5 | B |
| WP-2.3 | Ingest: CSV/XLSX/JSON readers, name normalization, null tokens, **text-first** type inference, date parsing, lossless Parquet v1 writer, content hash (ANALYTICS_SPEC §5) | L | 2.1, 2.2 | B |
| WP-2.4 | Profiling + PII suspicion (§6) | M | 2.3 | B |
| WP-2.5 | Semantic detection: scoring, assignment, validation, derived settings (`revenue_basis`, `discount`, `order_grain`) (§7 as revised) | L | 2.4, D-03 | B |
| WP-2.6 | Quality engine: four dimensions, missingness, duplicates, outliers, issue log, lineage rows (§8) | L | 2.5 | B |
| WP-2.7 | Cleaning engine: operation registry, preview, apply, canonical ordering, cleaning log, new-version writer (§9) | L | 2.6, 0.4 (§9) | B |
| WP-2.8 | EDA + stats: numeric/categorical/time/correlation/outliers + chart-spec selection (§11) | L | 2.5, 0.4 (§11) | B |
| WP-2.9 | Engine determinism + property suite: INV-01…12 applicable so far, thread-count 1 vs N, shuffle-invariance | M | 2.7, 2.8 | B |

**Gate G-ENGINE-1:** every engine function in scope has golden + property coverage; INV tests green; no framework imports (import-linter); the prototype's results on G8 are compared and every difference is explained in the PR.

## Phase 3 — Datasets and ingestion service (PRD Milestone 2)

| ID | Work package | Size | Needs | Lane |
|---|---|---|---|---|
| WP-3.1 | Migrations `0003_projects`, `0004_datasets_versions`, `0005_cleaning`, `0006_runs_and_jobs` (jobs framework is needed by ingest) + repositories | L | 1.5, 1.9 | A |
| WP-3.2 | Projects API + UI (list, create, settings: currency, locale) | M | 3.1, 1.12 | A→C |
| WP-3.3 | Celery app, queues (`ingest\|analysis\|generate\|light` + SQL pool per D-12), job lifecycle, retries, idempotency-key middleware, event publishing scaffold (Redis) | L | 3.1 | A |
| WP-3.4 | Upload flow: presigned multipart to MinIO, init/finalize, size/type limits, storage key layout | L | 3.3 | A |
| WP-3.5 | Ingest worker task: verify → engine ingest → Parquet v1 → profile → columns → semantic proposal → dataset `READY`; failure → coded errors | L | 3.4, 2.5 | A |
| WP-3.6 | Dataset API: list/get, versions, columns, **preview** (cursor), mapping GET/PUT with validation | L | 3.5 | A |
| WP-3.7 | Contract tests from OpenAPI (`schemathesis`) wired into `make gate` | S | 3.6 | D |
| WP-3.8 | Datasets UI: upload dialog with progress, dataset detail (schema + mapping editor with confidence/override, virtualized preview, version lineage card) | L | 3.6, 1.11 | C |
| WP-3.9 | E2E: upload golden CSV/XLSX/JSON → preview → edit mapping (Playwright, compose stack) | M | 3.8 | C |

**Gate G-M2 (tag `m2-dataset`):** a user uploads each supported format, sees preview and detected roles, overrides a role, and the dataset version hash verifies; foreign users get 404; failed ingests show coded, actionable errors.

## Phase 4 — Runs, pipeline, quality, cleaning, EDA (PRD Milestone 3)

| ID | Work package | Size | Needs | Lane |
|---|---|---|---|---|
| WP-4.1 | Migration `0007_quality_eda` + repositories | M | 3.1 | A |
| WP-4.2 | Pipeline framework in worker: stage DAG, `stage_runs`, `module_availability`, progress weights, cancel/retry, **run-key idempotency**, SSE endpoint with `Last-Event-ID` resume + heartbeat | L | 3.3, 2.1 | A |
| WP-4.3 | Stages `VALIDATING`, `PROFILING`, `CLEANING` (assessment) wired; quality report + issues persisted | L | 4.2, 4.1, 2.6 | A |
| WP-4.4 | Cleaning API: operations preview/apply → new version → lineage; cleaning log; recommendations | L | 4.3, 2.7 | A |
| WP-4.5 | `EDA` stage + EDA API (numeric, categorical, time, correlation, outliers) | L | 4.2, 2.8 | A |
| WP-4.6 | **ADR-013 chart library decision** → `ChartFrame` + chart components (line, bar, histogram, heatmap, donut) with 8 states, tokens, a11y | L | 1.11, D-16 | C |
| WP-4.7 | UI: run launcher + pipeline stepper (SSE hook with polling fallback), Data Quality page, Prepare (cleaning) page, EDA page | L | 4.4, 4.5, 4.6 | C |
| WP-4.8 | Integration: full run on G1–G7 through the API; reproducibility across worker restart; SSE resume test | M | 4.7 | D |

**Gate G-M3 (tag `m3-analytics`):** run → quality score with component breakdown and issue log → apply cleaning → new version with log → run again → EDA; same inputs give identical persisted values after a worker restart.

## Phase 5 — SQL sandbox and metric registry (PRD Milestone 4, part 1)

| ID | Work package | Size | Needs | Lane |
|---|---|---|---|---|
| WP-5.1 | **Adversarial safety corpus + sandbox conformance tests, written first** (SQL_SPEC §15.2, §15.4) | M | 0.5, D-12 | B |
| WP-5.2 | Validator: `sqlglot` pipeline, allow-lists, canonicalization, complexity limits, parameter rules | L | 5.1 | B |
| WP-5.3 | Sandbox executor: lockdown order, resource limits, interrupt, per-query temp dir, result wrapping; isolated SQL worker pool (no PG credentials, no egress) | L | 5.2, D-12 | A |
| WP-5.4 | Relations builder: `transactions`, `orders`, `customers`, `products`, `calendar`, `run_params`; RFM/segment views per D-01/D-02 | L | 5.3, 2.5 | B |
| WP-5.5 | Template registry + linter + metric bindings + **metric registry**; migration `0008_sql_metrics` (append-only `metrics`) | L | 5.4, 4.1 | B/A |
| WP-5.6 | `SQL_ANALYSIS` stage (template mode) → `sql_queries` + `metrics`; module availability | L | 5.5, 4.2 | A |
| WP-5.7 | SQL API (schema, validate, execute, questions, results, cancel, history) + metrics API + **evidence** endpoint | L | 5.6 | A |
| WP-5.8 | UI: SQL Explorer (editor, schema panel, question library, results, history) + **real Evidence Drawer** + `MetricRef` (display formatting identical to engine `format_display`) | L | 5.7, 1.11 | C |

**Gate G-M4a (tag `m4a-sql`):** the full adversarial corpus is rejected at validator **and** at bare engine; a template-produced metric opens in the drawer with its SQL, hash, and lineage; re-running the stored SQL on the same version returns identical values.

## Phase 6 — Retail analytics, insights, recommendations (PRD Milestone 4, part 2)

| ID | Work package | Size | Needs | Lane |
|---|---|---|---|---|
| WP-6.1 | Sales + Orders + Time modules (complete-period rules, growth) + Overview KPI/trend wiring | L | 5.7 | B→A |
| WP-6.2 | Customers + Loyalty + Purchase behavior modules | L | 6.1 | B→A |
| WP-6.3 | Segmentation + RFM (rules versioned) + Customers page (RFM heatmap, segment table, rules disclosure) | L | 6.2, D-01, D-02 | B→A→C |
| WP-6.4 | Products + Categories + Pareto + Products page | L | 6.1 | B→A→C |
| WP-6.5 | Geography + Discount + Payment modules + pages (association captions) | L | 6.1 | B→A→C |
| WP-6.6 | Module-availability matrix + partial-analysis UX; degraded-dataset matrix tests (missing each role) | M | 6.2–6.5 | D |
| WP-6.7 | Insight engine: rule catalog, confidence, ranking, template linter (no causal verbs), `insight_metrics`; migration `0009_insights_recommendations` | L | 6.6 | B |
| WP-6.8 | Recommendation engine + workflow API (`OPEN → IN_REVIEW → DONE`) | M | 6.7 | A |
| WP-6.9 | UI: real Overview dashboard, Insights page, Recommendations page | L | 6.8 | C |
| WP-6.10 | Cross-module invariants (INV-02, INV-03, orders reconcile, AOV identity), snapshot regression, report-language lint | M | 6.9 | D |

**Gate G-M4b (tag `m4b-analytics`):** every Retail module is available or explained-unavailable on every golden dataset; insights cite persisted metrics and open evidence; no number on any page originates outside the API.

## Phase 7 — Power BI package (PRD Milestone 5)

| ID | Work package | Size | Needs | Lane |
|---|---|---|---|---|
| WP-7.1 | Builder: dimensions with deterministic surrogate keys, Unknown members, `fact_sales`, reconciliation checks (POWERBI_SPEC §5–6, §9.4) | L | 6.10, D-11 | B |
| WP-7.2 | Package assembly: CSV (+ optional Parquet), M queries, relationships, `measures.dax/json`, `schema.json`, dashboard spec, theme, manifest, reference values, README; byte-identical ZIP | L | 7.1 | B |
| WP-7.3 | Verification: L0 lint and L1 Python reference evaluator in CI; L2 (Windows/Analysis Services) as a scheduled job (ADR-022) | L | 7.2 | D |
| WP-7.4 | Migration `0010_artifacts` (Power BI part) + `generate`-queue job + API + presigned download + audit | M | 7.2, 4.2 | A |
| WP-7.5 | UI: Power BI page (ERD, measures table, availability reasons, download, verification checklist) | M | 7.4 | C |

**Gate G-M5 (tag `m5-bi`):** a downloaded package imports into Power BI Desktop per the README and the eight required measures match `reference_values.json` (manual L3 check on G8 and one real dataset).

## Phase 8 — Reporting (PRD Milestone 6)

| ID | Work package | Size | Needs | Lane |
|---|---|---|---|---|
| WP-8.1 | `REPORTING_SPEC.md` + **ADR-014 PDF engine decision** | M | 6.10 | D |
| WP-8.2 | `ReportBundle` assembly + deterministic limitations logic (ANALYTICS_SPEC §19) | M | 8.1 | B |
| WP-8.3 | `AI_SPEC.md`, LLM gateway, **number-verification guard**, deterministic fallback; feature-flagged **off by default** | L | 8.2 | B |
| WP-8.4 | PDF generator | L | 8.2, 8.1 | B |
| WP-8.5 | DOCX generator | M | 8.2 | B |
| WP-8.6 | PPTX generator (speaker notes, chart images from chart specs) | L | 8.2 | B |
| WP-8.7 | Exports (cleaned dataset CSV/XLSX, metrics, SQL results), notifications, `0011_notifications_retention_audit` (remainder), generation jobs + downloads | L | 8.4–8.6 | A |
| WP-8.8 | UI: Reports page (generate, history, download, limitations panel) | M | 8.7 | C |
| WP-8.9 | Report-consistency test: every number in every generated file resolves to a persisted metric | M | 8.8 | D |

**Gate G-M6 (tag `m6-reporting`):** PDF, DOCX, PPTX generate from a completed run, open in their native viewers, and pass the consistency test; with the LLM flag off the output is complete and deterministic.

## Phase 9 — Production (PRD Milestone 7)

| ID | Work package | Size | Needs | Lane |
|---|---|---|---|---|
| WP-9.1 | Security hardening pass against `SECURITY.md`; headers/CSP; dependency/SAST/secret scans; sandbox review; **ADR-015 RLS decision** and implementation if accepted | L | 8.9 | A |
| WP-9.2 | Observability: structured logs, metrics, traces, dashboards, alerts; audit review | M | 8.9 | A |
| WP-9.3 | Retention and purge (DATABASE §12.3), backup/restore drill, `0012_grants` consolidation | M | 8.7 | A |
| WP-9.4 | Performance and load: 1 M / 5 M row datasets, p95 targets, OOM/queue-stall chaos, backpressure | L | 8.9 | D |
| WP-9.5 | Accessibility audit (WCAG 2.2 AA): automated + keyboard + screen reader | M | 8.8 | C |
| WP-9.6 | Full-journey E2E (PRD §131), cross-browser, responsive checks | M | 9.5 | C |
| WP-9.7 | `DEPLOYMENT.md`, production images, deploy manifests/IaC, migrate-on-deploy, health checks, rollback | L | 9.1–9.3 | A |
| WP-9.8 | Documentation + release: runbooks, API docs, changelog, **PRD §124/§125/§126 conformance audit** (`/audit-shortcuts`), release candidate | M | 9.4, 9.6, 9.7 | D |
| WP-9.9 | *(Optional, P2)* Port the landing page and 3D factory scene to Next.js | M | 9.8 | C |

**Gate G-M7 (tag `m7-production` / release candidate):** every item of the PRD §124 completion list maps to a passing test (§11); load, security, and accessibility reports are attached; production build deploys from scratch with one command.

---

# 6. Phase Notes — Acceptance Criteria and Pitfalls

Only the packages where agents most often go wrong are expanded. Every package also inherits the gates in §4.

## Phase 1 — Foundation

- **WP-1.1** Pin the Python version after checking that every planned dependency (Polars, DuckDB, PyArrow, `sqlglot`, `argon2-cffi`, a Postgres driver, Celery) installs and passes its test suite on it. Commit `uv.lock` and `pnpm-lock.yaml`. `import-linter` contracts must fail the build if `insightforge_engine` imports `fastapi`, `celery`, `sqlalchemy`, or `apps.*`.
- **WP-1.4** Enum values exist in exactly one place; the TypeScript union types and the DB `CHECK` lists are generated or verified against it. A test fails if they diverge.
- **WP-1.5** Include UUIDv7 generation, the `forbid_update_delete` trigger helper, and composite `(id, owner_id)` foreign keys exactly as DATABASE §3–§6 specify. Round-trip every migration (`up → down → up`). Apply the grants function inside the test harness so tests run as the **application role**, not a superuser.
- **WP-1.7** Responses must not reveal whether an email exists. Cookie flags `HttpOnly`, `Secure`, `SameSite` per API_SPEC §3. Rotate the session on login. Rate-limit login and reset per IP and per account. Every auth event writes an audit row without secrets.
- **WP-1.9** Every repository method takes an owner scope; there is no unscoped query path. The cross-tenant fixture is reused by every later package: *create resource as A, request as B, expect `404`*.
- **WP-1.10 / 1.11** Tailwind uses design **tokens only**; a lint rule rejects raw hex values and arbitrary pixel colors outside the token file. Add a test that fails if a JSX file contains a numeric literal rendered as a business figure (allow-list for layout constants).

## Phase 2 — Engine core I

- **WP-2.1** `common/` is the only place that formats numbers for display; the web client's formatter is tested against the same golden fixtures (INV-10).
- **WP-2.2** Fixtures include expected values computed **by hand or by an independent implementation**, never by running the code under test. G1 is the PRD §81 three-row dataset (Customer A ₹100 + ₹200, Customer B ₹300 → total ₹600). Keep `fixtures/README.md` listing, per fixture, which behaviors it covers (refunds, ties, single-customer data, partial months, gap months, missing roles, NULL categories, derived revenue, messy headers).
- **WP-2.3** Read **everything as text**, infer types yourself, store version 1 losslessly (typed only when 100 % parse). Keep the Parquet writer settings pinned. Test encodings, delimiters, Excel dates, leading-zero identifiers, and `NA` country codes.
- **WP-2.5** Test conflict resolution (two columns claim one role), the sole-date-column rule, and that LLM suggestion never displaces a rule/user assignment. Mapping hash must ignore column order.
- **WP-2.6** The score must be explainable: each dimension returns its components with applicable base, affected counts, and penalty points. Outliers and accuracy indicators do **not** enter the score.
- **WP-2.7** Operations execute in canonical order regardless of request order; no-op operations are logged and do not create a version; money columns are never imputed by default.
- **WP-2.9** Run the same pipeline with 1 and N threads and compare every persisted decimal string byte for byte.

## Phase 3 — Datasets and ingestion

- **WP-3.1** Land migrations 0003–0006 together: the jobs framework is needed by the ingest worker even though runs come later.
- **WP-3.4** Upload goes directly to object storage; the API only issues presigned parts and finalizes. Finalize verifies size and hash, sniffs content (not just the extension), rejects macro-enabled workbooks, and enforces zip-expansion limits (XLSX is a zip archive).
- **WP-3.5** The worker streams; memory limits per task come from config. A failure produces a coded, user-actionable error and leaves no half-written version.
- **WP-3.6** Preview uses cursor pagination and is capped; mapping updates run the same validation as detection and return `MAPPING_INVALID` with a reason.

## Phase 4 — Runs, quality, cleaning, EDA

- **WP-4.2** Run key = hash of (version, config, pipeline version, domain, mapping). A duplicate request returns the existing live or completed run. Retry semantics follow D-08/D-09 (resume the same run, reset terminal fields atomically). SSE: event ids, `Last-Event-ID` replay, heartbeat, and a polling fallback exercised by a test that kills the stream.
- **WP-4.4** Applying cleaning never touches version *n*; it writes version *n+1*, a log, and carries the mapping forward by column name.
- **WP-4.6** Choose the library, then wrap it: no page imports the chart library directly. Every chart has loading, empty, error, partial, and unavailable states, a text alternative, and caps at 1,000 plotted points with the aggregation grain shown.
- **WP-4.8** Reproducibility test: run, restart workers, run again with the same key → identical metrics, identical `run_key`, no new rows.

## Phase 5 — SQL

- **WP-5.1 comes before any sandbox code.** The corpus is the specification of the sandbox. Run it against both the validator and a bare locked-down connection.
- **WP-5.3** Follow the lockdown order in SQL_SPEC §4.1 exactly (create views → restrict paths → disable external access → lock configuration). Verify on the pinned DuckDB version that views over allow-listed files keep working; otherwise use the documented in-memory materialization fallback. Resolve the persistence path in D-12 first: a worker with no database credentials cannot write `sql_queries` itself.
- **WP-5.4** Columns for unmapped roles are **absent**, not NULL. Build `calendar` and `run_params` in trusted setup only.
- **WP-5.5** The template linter parses every template, checks allow-lists, declared parameters, total `ORDER BY`, explicit aliases, and that declared outputs equal the executed projection on golden data. `metrics` is append-only (trigger from DATABASE §6.7).
- **WP-5.8** The Evidence Drawer shows metric, formatted value, formula, SQL, dataset hash, and the lineage stepper — all read from the evidence endpoint, nothing literal.

## Phase 6 — Retail analytics

- **WP-6.1** Growth uses only complete, consecutive periods and returns *no row* (→ unavailable with a reason), never `0`. Partial periods are returned flagged for chart annotation.
- **WP-6.3** Segments are mutually exclusive and sum to the customer total (INV-03). Test degenerate cases explicitly: every customer a one-time buyer (G6), tied recency, fewer than the minimum number of customers.
- **WP-6.7** The template linter blocks causal verbs ("drives", "causes", "leads to"); association insights carry the association flag; confidence and ranking follow the ANALYTICS_SPEC formulas.
- **WP-6.10** Property tests: category + unclassified revenue = total revenue; orders reconcile to total; AOV identity; Pareto monotonic; shuffling input row order changes nothing.

## Phase 7 — Power BI

- **WP-7.1** Surrogate keys are dense ranks of sorted natural keys; Unknown member `-1`; blank (not Unknown) customer and date keys; reconcile row counts and `SUM(revenue)` before writing anything.
- **WP-7.2** ZIP entries sorted, timestamps fixed, compression pinned → byte-identical packages. Use `DISTINCTCOUNTNOBLANK` where SQL ignores NULLs.
- **WP-7.3** The L1 reference evaluator is a separate implementation from the builder; it is what catches a measure/data-contract mismatch in standard CI.

## Phase 8 — Reporting

- **WP-8.2** Limitations are produced by deterministic checks (missing data above threshold, small samples, derived revenue, association-only findings), never free text.
- **WP-8.3** The guard rejects any LLM sentence containing a number that does not match a persisted metric's formatted value; on rejection, fall back to the template text. The product must be fully usable with the flag off.
- **WP-8.9** Parse each generated PDF/DOCX/PPTX, extract numbers, and assert each resolves to a metric ID present in the run.

## Phase 9 — Production

- **WP-9.4** Targets come from PRD §119 and SQL_SPEC §13; record actual p50/p95 and memory for 1 M and 5 M rows.
- **WP-9.8** `/audit-shortcuts` greps for hardcoded figures, auth bypasses, `TODO`/mock responses, unrestricted SQL, and `DELETE` on dataset versions; findings block the release.

---

# 7. Critical Path and Schedule

**Critical path:** 0.3 → 0.4 → 2.1 → 2.3 → 2.5 → 3.4 → 3.5 → 4.2 → 5.3 → 5.5 → 5.6 → 6.1 → 6.6 → 6.7 → 7.1 → 7.2 → 8.2 → 8.4 → 9.7 → 9.8.

Anything on this path that slips moves the release. Packages off the path (UI polish, optional features, WP-9.9) are the first to defer.

**Target cumulative weeks** for one developer driving three lanes (heuristic; re-plan at every gate):

| Gate | Target week | Lanes busy |
|---|---:|---|
| G0 spec closure | 2 | D |
| G-M1 | 4 | A, C (B starts engine skeleton) |
| G-ENGINE-1 | 7 | B |
| G-M2 | 9 | A, C |
| G-M3 | 12 | A, B, C |
| G-M4a | 14 | B, A, C |
| G-M4b | 18 | B, A, C |
| G-M5 | 20 | B, D, C |
| G-M6 | 23 | B, A, C |
| G-M7 | 26 → compress to 24 by overlapping 9.1–9.3 with Phase 8 | A, D, C |

**Rule for every gate review (30 minutes):** (1) demo the vertical slice in the real UI against real data; (2) read the test report; (3) spot-check three numbers against an independent calculation; (4) update `DECISIONS.md` and the changelog; (5) tag.

---

# 8. Specification Slices (what each package may read)

Open only the named sections; use `docs/SPEC_INDEX.md` for line ranges.

| Packages | Read these slices |
|---|---|
| WP-1.1 – 1.3 | `ARCHITECTURE` §5, §6, §16, §20; `PRD` §125–126 |
| WP-1.4 – 1.6 | `DATABASE` §2–§4, §6.1, §15; `API_SPEC` §2, §4 |
| WP-1.7 – 1.9 | `API_SPEC` §3, §5, §10; `ARCHITECTURE` §12–§13; `SECURITY`; `DATABASE` §6.1, §8, §11 |
| WP-1.10 – 1.12 | `DESIGN` tokens, components, UI states; `ARCHITECTURE` §15; `API_SPEC` §15 |
| WP-2.1 – 2.9 | `ANALYTICS_SPEC` §2–§11; `ARCHITECTURE` §8.1–§8.6; `DATABASE` §6.3–§6.6 (field shapes only) |
| WP-3.1 – 3.3 | `DATABASE` §6.2–§6.5, §9; `ARCHITECTURE` §9; `API_SPEC` §6 |
| WP-3.4 – 3.9 | `ARCHITECTURE` §10.1–§10.3; `API_SPEC` §7.3–§7.5; `DESIGN` dataset pages |
| WP-4.1 – 4.8 | `API_SPEC` §6, §7.6–§7.9; `ARCHITECTURE` §8.3, §9, §18; `DATABASE` §6.4–§6.6; `DESIGN` quality/prepare/EDA pages and chart rules |
| WP-5.1 – 5.4 | `SQL_SPEC` §3–§8, §12–§15; `ARCHITECTURE` §10.5; `SECURITY` |
| WP-5.5 – 5.8 | `SQL_SPEC` §9–§11; `ARCHITECTURE` §8.4; `API_SPEC` §7.10, §7.12; `DATABASE` §6.7; `DESIGN` evidence drawer |
| WP-6.1 – 6.6 | `SQL_SPEC` §5.5–§5.8, §10; `ANALYTICS_SPEC` §12–§16; `API_SPEC` §7.11; `ARCHITECTURE` §8.7–§8.8 |
| WP-6.7 – 6.10 | `ANALYTICS_SPEC` §14–§15; `ARCHITECTURE` §8.9; `API_SPEC` §7.13; `DATABASE` §6.8; `DESIGN` insight cards |
| WP-7.1 – 7.5 | `POWERBI_SPEC` (all); `ARCHITECTURE` §14.4–§14.5; `API_SPEC` §7.14; `DATABASE` §6.9 |
| WP-8.1 – 8.9 | `ARCHITECTURE` §11, §14.1–§14.3; `API_SPEC` §7.15–§7.18; `REPORTING_SPEC`; `AI_SPEC` |
| WP-9.1 – 9.8 | `ARCHITECTURE` §13, §16–§19, §21; `DATABASE` §11–§12, §14, §16–§17; `SECURITY`; `DEPLOYMENT` |

---

# 9. Risk Register

| # | Risk | Likelihood | Mitigation (built into the plan) |
|---|---|---|---|
| R1 | Agents drift from the specifications | High | Slice-limited prompts, `/spec-check`, API-inventory and enum-parity tests in `make gate` |
| R2 | Hardcoded numbers or fake responses carried over from the prototype | High | WP-0.2 audit, numeric-literal guard test in the web package, `/audit-shortcuts` at WP-9.8 |
| R3 | Non-determinism after library upgrades or thread changes | Medium | Pinned lockfiles, INV-07 test with 1 vs N threads, golden snapshot diffs require version bumps |
| R4 | SQL sandbox escape | Low, severe | Corpus-first development, engine-level lockdown, isolated SQL pool, security review in WP-9.1 |
| R5 | SQL worker has no DB credentials yet must persist results | Certain (spec gap) | Decision D-12 before WP-5.1; coordinator persists results |
| R6 | Context overload for agents (≈ 330 KB of specs) | High | Spec slices, `SPEC_INDEX`, one package per conversation |
| R7 | Dependency/wheel gaps on the newest Python | Medium | Compatibility check in WP-1.1; pin to a supported minor |
| R8 | Scope creep into P2 (AI SQL, map visuals, search, landing animation) | Medium | Priority labels (PRD §128); WP-9.9 last; feature flags default off |
| R9 | Power BI L2 verification needs a Windows runner | Certain | L0/L1 in CI; L2 scheduled; manual L3 at the gate |
| R10 | Single-reviewer bottleneck | High | S/M/L sizing, mandatory artifacts, machine gates before human review |
| R11 | Large-file memory failures | Medium | Streaming ingest, per-task limits, chaos tests in WP-9.4 |
| R12 | Agent rate limits or quota exhaustion mid-package | Medium | Keep packages small; commit at green points; resume from the plan artifact |

---

# 10. Decision Backlog (write into `DECISIONS.md` in WP-0.3)

Recommendations come from reading all seven specifications together; accept or amend each.

| ID | Decision needed | Recommendation | Needed before |
|---|---|---|---|
| D-01 | RFM scoring (SQL_SPEC §5.7 uses `NTILE` + ID tie-break; tied customers get different scores) | Use mid-rank percentile scoring: tied values share a score; a fully tied dimension gets the neutral middle score. Implementable with allow-listed window functions in the `customer_rfm` view; Power BI and reports consume that one view | WP-5.4 |
| D-02 | Segmentation rules on degenerate data (with neutral scores, `f ≥ 3 or m ≥ 3` would make everyone *Regular*) | Re-express rules with raw guards (e.g., Regular requires ≥ 2 orders or a high monetary score); verify on G5/G6 | WP-6.3 |
| D-03 | Discount handling (SQL_SPEC §5.8 vs ANALYTICS_SPEC `AMOUNT`/`FLAG` kinds) | Allow amount → percent conversion during cleaning when price and quantity exist; otherwise Discount unavailable; drop `FLAG` kind | WP-2.5 |
| D-04 | Relation names and ownership (`customers`, `products`, `calendar` vs `*_dim`) | SQL_SPEC §5 wins; ANALYTICS_SPEC §10 references it | WP-0.4 |
| D-05 | Meaning of the `TRANSFORMING` stage | Builds no dataset version; relations are connection-time views; derived Parquet only when materialization is needed; `TRANSFORMED` version kind unused in V1 | WP-4.2 |
| D-06 | Outlier "Explained" state vs DB `handling` enum | Persist `FLAGGED` + `details.explanation`; Keep/Flag stored in `details.user_decision` (add an issue-decision endpoint to API_SPEC); Exclude is a cleaning operation | WP-2.6 |
| D-07 | Loyalty module missing from ARCHITECTURE §8.8 and the API | Add the module row and an `analytics/loyalty` view; SQL_SPEC §10.10 already defines its templates | WP-6.2 |
| D-08 | Retrying a failed module inside a `COMPLETED` run | Add `POST /analysis-runs/{id}/modules/{module}/retry`; reset terminal fields atomically on whole-run retry | WP-4.2 |
| D-09 | Report/deck/Power BI stages vs "run must be COMPLETED" | Stage rows stay `SKIPPED` unless requested at run creation; artifacts have their own lifecycle | WP-4.2 |
| D-10 | PPTX in `presentations` vs "reports" in the UI/dashboard counts | Present one combined history; count both | WP-8.7 |
| D-11 | AOV differs between global and `pay_summary`/`disc_band_summary` when `transaction_id` is NULL | Add `transaction_id IS NOT NULL` to those templates; bump `PIPELINE_VERSION` | WP-5.5 |
| D-12 | SQL worker: (a) queue (ADR-017 SQL), (b) how results are persisted without DB credentials, (c) `CANCELLED` status (ADR-018) | (a) dedicated `sql` queue via migration; (b) worker writes result + signed envelope to object storage and signals via Redis, a trusted coordinator task persists; (c) add `CANCELLED` | WP-5.1 |
| D-13 | Migration order | Ship `audit_events` with the identity migration; use `0012_grants` and run the grants function in the test harness from the start | WP-1.5 |
| D-14 | Numeric policy (ADR-016) | Money exact `DECIMAL(38,10)`; statistics float64; ratios as fractions in [0,1]; persisted with half-even rounding | WP-2.1 |
| D-15 | ADR numbering collision (ADR-017 used twice; XLSX reader needs an ID) | Renumber the XLSX-reader decision to ADR-024; ADR-020–023 stay with Power BI | WP-0.3 |
| D-16 | ADR-013 chart library | ECharts behind `ChartFrame` (native heatmap, combo, large series); Recharts acceptable if heatmaps are custom | WP-4.6 |
| D-17 | ADR-014 PDF engine | WeasyPrint with server-rendered SVG charts (no browser in the worker image); Chromium only if layout fidelity demands it | WP-8.1 |
| D-18 | ADR-015 Row-Level Security | DATABASE §11 already designs it; implement as defense in depth in WP-9.1 once scoped-repository tests are complete | WP-9.1 |
| D-19 | Python/DuckDB versions | Newest minor where every dependency has wheels and the sandbox conformance suite passes; commit lockfiles | WP-1.1 |
| D-20 | Wire-shape conflicts (`/auth/csrf` public vs session; `SESSION_EXPIRED` vs `AUTH_SESSION_EXPIRED`; pagination envelope; upload init path) | API_SPEC wins everywhere; update ARCHITECTURE | WP-1.4 |
| D-21 | Time zone | V1 stores `purchase_date` in UTC (SQL_SPEC); configurable reporting zone deferred to P2 | WP-0.4 |
| D-22 | Example insight titles in PRD/DESIGN/API use "drive" | Change examples to "account for"; the language linter enforces it | WP-6.7 |
| D-23 | Zero-filled vs gapped time series (SQL fills empty days with 0; DESIGN shows gaps for missing data) | Zero-fill inside the data range (no sales occurred), annotate partial edge periods, never extrapolate | WP-6.1 |

---

# 11. Completion Mapping (PRD §124)

| PRD §124 item | Delivered by | Proven by |
|---|---|---|
| Register, login, Google auth | WP-1.7, 1.8, 1.12 | Auth E2E; cross-tenant matrix |
| Create a project | WP-3.2 | E2E |
| Upload supported datasets; validation; preview | WP-3.4 – 3.8 | WP-3.9 E2E; contract tests |
| Profiling; data quality; cleaning; dataset versioning | WP-2.4 – 2.7, 4.3, 4.4 | Golden + G-M3 reproducibility |
| EDA | WP-2.8, 4.5, 4.7 | Golden + E2E |
| SQL analytics | WP-5.1 – 5.8 | Safety corpus; template lint; parity |
| Retail analytics; segmentation; RFM where possible | WP-6.1 – 6.6 | Module matrix; invariants |
| Insights evidence-backed; recommendations generated | WP-6.7 – 6.9 | Evidence-resolution test; language linter |
| Power BI model generated | WP-7.1 – 7.5 | L0/L1 in CI; L3 manual |
| Reports; PPTX | WP-8.4 – 8.8 | WP-8.9 consistency test |
| Background jobs; errors handled | WP-3.3, 4.2 | Retry/cancel/SSE tests; error-catalog test |
| Authorization works | WP-1.9 + every package | Cross-tenant fixture in every API test file |
| Tests pass; production build works | WP-9.4 – 9.8 | CI release job from a clean checkout |

---

# Appendix A — Prototype → Production Mapping

| Prototype file | Production destination | Action | Work package |
|---|---|---|---|
| `types.py` | `packages/shared_schemas` + engine-local dataclasses | Rewrite; enums from the DB source | 1.4, 2.1 |
| `sample_data.py` | `tests/golden/G8` generator with a fixed seed | Keep as fixture | 2.2 |
| `ingestion.py` | `ingest/` | Refactor (text-first typing, lossless v1) | 2.3 |
| `quality.py` | `quality/` | Rewrite to ANALYTICS_SPEC §8 | 2.6 |
| `cleaner.py` | `cleaning/` | Rewrite (flag-only default, canonical order) | 2.7 |
| `schema_mapper.py` | `semantics/` | Rewrite (scoring, validation, enum names) | 2.5 |
| `eda.py` | `eda/`, `stats/` | Refactor against the spec definitions | 2.8 |
| `rfm.py` | SQL `customer_rfm` / `customer_segments` + engine tests | Replace (D-01, D-02) | 5.4, 6.3 |
| `product_analytics.py` | SQL templates `prod_*`, `cat_*` | Replace | 6.4 |
| `sql_sandbox.py` | `sqlgen/validator`, sandbox executor | Rewrite (allow-list, lockdown) | 5.2, 5.3 |
| `star_schema.py` | `powerbi/` builder | Rewrite (names, ZIP package, manifest) | 7.1, 7.2 |
| `insights.py` | `insights/` rule engine | Rewrite (rules, confidence, linter) | 6.7 |
| `pipeline.py` | `pipeline/` + Celery stages | Rewrite (persistence, idempotency, SSE) | 4.2 |
| `server.py` | `apps/api`, `workers/` | Discard | 1.6 onward |
| `workspace.html`, `auth.html`, `index.html`, `factory.js` | `apps/web` | Archive; rebuild per page | 1.10 onward; 9.9 |

---

# Appendix B — `GEMINI.md` / `AGENTS.md` Template

```markdown
# InsightForge — Project Constitution

You are building InsightForge, an evidence-first retail analytics platform. The specifications in `docs/` are the
source of truth. Read only the sections your work package names (see docs/SPEC_INDEX.md).

## Non-negotiables
1. Python/SQL/statistics produce every number. The UI, reports, decks, Power BI and AI text only reference persisted
   metrics by ID. Never hardcode analytics results, insights, or API responses outside tests/.
2. Raw datasets are immutable. Any change creates a new version + a cleaning-log entry.
3. SQL runs only through the validator and the DuckDB sandbox. No string-built SQL, ever.
4. Every owned-resource access goes through scoped repositories. Foreign resources return 404.
5. Unavailable is not failed: missing prerequisites produce an explained "unavailable" result.
6. Association is not causation. Never write causal language in generated text.
7. No secrets in source; no stack traces, secrets, or raw data in logs or error responses.
8. No authentication bypass and no demo shortcuts.

## How to work
- One work package per conversation. Start with /start-wp, finish with /finish-wp.
- Write the tests from the spec first when the package produces numbers (golden, property, safety corpus).
- If the spec is silent or contradictory, STOP. Add a proposal to docs/DECISIONS.md and ask.
- Do not add dependencies without a one-line justification in the PR description.
- `make gate` must be green before you say a package is done. Never skip or loosen tests to pass it.
- Never run destructive commands without asking (rm -rf, git push --force, DROP/TRUNCATE).
```

# Appendix C — Rule Files (contents, abbreviated)

| File | Key rules |
|---|---|
| `10-engine.md` | No imports of `fastapi`, `celery`, `sqlalchemy`; money as `Decimal`/DuckDB `DECIMAL(38,10)`; every persisted ordering has a total order with a unique tie-breaker; no clock, randomness, or network; seeded sampling only; `PIPELINE_VERSION` bump rules |
| `20-api-db.md` | Closed error catalog and standard envelope; idempotency key on listed endpoints; `If-Match` on updates; cursor pagination; composite owner foreign keys; migrations reversible; never edit an applied migration |
| `30-web.md` | Design tokens only; no business numbers in source; every data view implements loading/empty/error/partial/unavailable/stale/forbidden/success; charts only through `ChartFrame`; keyboard and screen-reader support |
| `40-testing.md` | Golden expected values are independent of the code under test; property tests for invariants; one cross-tenant test per endpoint; a snapshot change requires a version bump and a stated reason |
| `50-security.md` | Upload content sniffing and size limits; presigned URLs short-lived; log redaction; PII-suspected columns never reach prompts or logs; sandbox has no credentials or egress |

# Appendix D — Workflows (slash-invoked saved prompts)

| Workflow | Behavior |
|---|---|
| `/start-wp <id>` | Read the package row in `IMPLEMENTATION_PLAN.md` §5 and its spec slices in §8; list ambiguities; produce an implementation-plan artifact with files to create and tests to write first; wait for approval |
| `/finish-wp` | Run `make gate`; attach the output; fill the conformance checklist (spec sections implemented, errors cataloged, authz tests added, docs updated, versions bumped); list deferred items |
| `/spec-check` | Run the inventory/enum-parity scripts; compare implemented endpoints, enum values, and metric names with `API_SPEC`, `DATABASE`, `SQL_SPEC`; report mismatches without "fixing" the spec |
| `/new-migration` | Create a reversible Alembic revision in the correct numeric slot, update the DB tests, run the round-trip |
| `/new-endpoint` | Scaffold route + schema + service + repository + authz test + inventory entry + generated client |
| `/new-metric` | Scaffold template + binding + golden fixture + independent reference calculation + evidence text |
| `/golden-update` | Show the snapshot diff, require a justification, and bump the right version |
| `/audit-shortcuts` | Search for hardcoded figures, auth bypasses, mock responses, unrestricted SQL, and dataset-version deletes; fail on any finding |

# Appendix E — Package Prompt Template and Samples

**Template**

```text
/start-wp WP-<id>

Goal: <one sentence from the plan>
Read only: <spec slices from §8>
Depends on (already merged): <packages>
Deliver: <files/modules, tests, docs>
Tests first: <golden / property / corpus items>
Out of scope: <explicit exclusions>
Done when: make gate is green and the conformance checklist is complete.
If the spec is unclear, stop and write a proposal in docs/DECISIONS.md.
```

**WP-2.3 (Ingest)**

```text
/start-wp WP-2.3
Goal: implement ingest per ANALYTICS_SPEC §5 (text-first reads, name normalization, null tokens, type inference,
date parsing, lossless Parquet v1 with content hash).
Read only: ANALYTICS_SPEC §3–§5; ARCHITECTURE §8.1–§8.2; DATABASE §6.3 (dataset_columns fields).
Tests first: fixtures G2 (messy headers/dates), leading-zero IDs, "NA" country code, Indian/European number formats,
XLSX native dates, 0.1% malformed CSV rows, rejection of macro workbooks.
Out of scope: profiling, semantics, any API or database code.
Done when: golden tests pass, thread-count determinism test passes, import-linter passes.
```

**WP-5.1 (Sandbox corpus first)**

```text
/start-wp WP-5.1
Goal: build the adversarial SQL corpus and sandbox conformance tests BEFORE any sandbox implementation.
Read only: SQL_SPEC §4, §7, §15.2, §15.4.
Deliver: tests/sql_safety/corpus.yaml (statement, expected issue code), a parametrized test that runs each statement
through (a) the validator and (b) a bare locked-down DuckDB connection, and a conformance suite for lockdown.
Tests are expected to fail until WP-5.2 and WP-5.3 land; mark them xfail with the owning package id.
Out of scope: validator and executor implementation.
```

# Appendix F — Documents Still to Write and When

| Document | Write during | Needed by |
|---|---|---|
| `DECISIONS.md` | WP-0.3 (then continuously) | WP-1.4 |
| `ANALYTICS_SPEC.md` §1–10 revisions + §9–25 | WP-0.4 | WP-2.1 (§3–4), WP-2.5–2.8 (§5–11), WP-6.x (§12–16), WP-6.7 (§14–15), WP-8.2 (§19) |
| `TESTING.md` | WP-0.5 | WP-2.2 |
| `SECURITY.md` | WP-0.6 | WP-1.7 |
| `REPORTING_SPEC.md` | WP-8.1 | WP-8.2 |
| `AI_SPEC.md` | WP-8.3 | WP-8.3 |
| `DEPLOYMENT.md` | WP-9.7 | WP-9.7 |

# Appendix G — Revisions Required in `ANALYTICS_SPEC.md` (§1–10) After Reading `SQL_SPEC` and `POWERBI_SPEC`

1. §3.3/§10: replace the planned Python-built `customers_dim`, `products_dim`, `date_dim` with the SQL_SPEC §5 relations; TRANSFORMING builds no version (D-05).
2. §4.5: remove the configurable reporting time zone; `purchase_date` is UTC (D-21).
3. §3.5: `line_id` is **1-based** (POWERBI_SPEC §5.4) — align.
4. §7.6: remove the `FLAG` and `AMOUNT`-only discount kinds; follow SQL_SPEC §5.8 with the conversion rule in D-03.
5. §1.4/§24: renumber the XLSX-reader ADR (D-15); adopt SQL_SPEC top-N (20) and `__OTHER__` naming, plus the `revenue_unclassified` metric.
6. §12–15 (to be written): adopt SQL_SPEC §11.3 metric names; Spearman stays in Python (EDA), Pearson for the discount metric stays in SQL; segmentation and RFM follow D-01/D-02; time series are zero-filled inside the data range (D-23).
7. §8: keep the scoring methodology; add the lineage rows and outlier representation from D-06.
8. §19: report limitations must include "derived revenue", "first month excluded from new-customer headline", and "snapshot attributes as of reference date" (POWERBI_SPEC §5.5).

# Appendix H — `Makefile` Skeleton

```makefile
.PHONY: gate lint types test golden migrate-check inventory web-test e2e up down seed-dev

gate: lint types test golden migrate-check inventory web-test
	@echo "GATE OK"

lint:           ; uv run ruff check . && uv run import-linter && pnpm -r lint
types:          ; uv run mypy packages apps workers && pnpm -r typecheck
test:           ; uv run pytest -m "not golden and not e2e"
golden:         ; uv run pytest -m golden
migrate-check:  ; scripts/migration_roundtrip.sh
inventory:      ; uv run python scripts/spec_inventory.py
web-test:       ; pnpm -r test
e2e:            ; docker compose -f infra/compose/docker-compose.test.yml up -d --wait && pnpm --filter web e2e
up:             ; docker compose -f infra/compose/docker-compose.dev.yml up -d
down:           ; docker compose -f infra/compose/docker-compose.dev.yml down
seed-dev:       ; uv run python scripts/seed_dev_user.py   # creates a real account; logs in through the normal flow
```
