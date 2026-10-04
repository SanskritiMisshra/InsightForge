# InsightForge — SQL Analytics Specification (SQL_SPEC.md)

**Version:** 1.0
**Status:** Authoritative for the SQL analytics layer (relations, templates, validation, sandbox, execution)
**SQL dialect:** DuckDB (analytical engine) — validated and canonicalized with `sqlglot` (`dialect="duckdb"`)
**Depends on:** `PRD.md` (§46–51, §60, §81, §95–97, §112–114, §126), `ARCHITECTURE.md` (§8.4, §10.5, §11, §13), `DATABASE.md` (§6.7 `sql_queries`, `metrics`), `API_SPEC.md` (§7.12)
**Companion documents:** `ANALYTICS_SPEC.md` (thresholds, scoring, metric semantics), `POWERBI_SPEC.md` (DAX parity), `SECURITY.md`, `TESTING.md`

> **Authority rule.** This document is authoritative for the **SQL text, relations, safety rules, and execution behavior**. `ANALYTICS_SPEC.md` is authoritative for **business definitions and thresholds** that the SQL consumes as parameters (e.g., segmentation cut-offs, minimum sample sizes). If the two conflict, the conflict must be identified and resolved before implementation continues (PRD §127). Any change to template SQL or relation definitions **bumps `PIPELINE_VERSION`** and `sql_spec_version` (§16).

---

# 1. Purpose and Scope

SQL is one of InsightForge's two deterministic sources of numerical truth (the other being the Python statistics layer). This specification defines:

1. The **analytical environment** in which SQL runs and why it is isolated from the application database (§3–4).
2. The **relations** (tables/views) exposed to SQL and their exact schemas (§5–6).
3. The **query template library** — the questions the platform answers, with exact SQL (§9–10).
4. How SQL results become **verified metrics** (§11).
5. The **validation and sandbox rules** that make user- and AI-supplied SQL safe (§7–8).
6. Execution, limits, result handling, error mapping, auditing, performance, testing, and versioning (§12–16).

## 1.1 Principles (from the PRD)

| Principle | SQL consequence |
|---|---|
| Accuracy over appearance (§5.1) | Every number shown comes from a query with a known calculation; golden tests verify results |
| Evidence before explanation (§5.2) | Each metric persists its `sql_query_id`; the Evidence Drawer shows the SQL (API_SPEC §7.10) |
| Reproducibility (§5.4, §95) | Same dataset-version bytes + same SQL + same parameters ⇒ identical result; non-deterministic functions are forbidden |
| No unrestricted SQL (§48) | Single read-only `SELECT`, allow-listed relations/functions, sandboxed engine, no network/file access |
| One source of truth (§60, §96) | Reports/Power BI/insights consume persisted metrics produced here — they never re-query or re-compute |
| Partial analysis (§65) | Templates declare required semantic roles; unavailable templates are reported with reasons, never faked |
| Precision preserved (§114) | Monetary values use `DECIMAL(38,10)`; rounding/formatting only at presentation |

---

# 2. Terminology

| Term | Meaning |
|---|---|
| **Relation** | An allow-listed table or view available to SQL (`transactions`, `orders`, …) |
| **Role** | A semantic column role (`REVENUE`, `CUSTOMER_ID`, …) from `DATABASE.md` §4 |
| **Template** | A registered, parameterized query owned by the domain plugin (`retail`), identified by a stable `key` |
| **Interactive query** | A user-submitted (or AI-generated, P2) `SELECT` executed through the sandbox |
| **Sandbox** | The isolated DuckDB execution context (§4) |
| **Canonical SQL** | The SQL regenerated from the validated AST; **this**, never the raw user text, is what executes |
| **Metric binding** | A declared mapping from a template output column to a persisted metric (§11) |

---

# 3. Analytical Environment

## 3.1 Decision recap (ARCHITECTURE §10.5, ADR-005)

SQL analytics run on **DuckDB** over **Parquet snapshots of a specific dataset version** — **not** on the application PostgreSQL. Consequences:

- Application tables (`users`, `sessions`, other tenants' data) are **physically unreachable** from SQL (PRD §48).
- Queries are reproducible: the dataset version is immutable and hash-verified.
- Columnar execution is fast for aggregate analytics without loading data into Postgres.
- The SQL sandbox holds **no credentials** for PostgreSQL and has **no network egress**.

## 3.2 Execution topology

```text
 API (validate request, authorize, persist sql_queries row QUEUED)
        │ enqueue
        ▼
 Celery worker pool "sql"  (no PG credentials, no egress; reads object storage via pre-fetched local copy)
        │
        ├─ 1. Fetch dataset-version Parquet to ephemeral private dir; verify sha256 == dataset_versions.content_sha256
        ├─ 2. Open in-memory DuckDB; TRUSTED SETUP builds base relations (§5) from the Parquet
        ├─ 3. Apply lockdown (§4) — configuration locked, external access disabled
        ├─ 4. Validate user SQL (§7) → canonical SQL
        ├─ 5. Execute with parameters, timeout, memory & row caps
        ├─ 6. Persist result (bounded) + metadata → sql_queries; emit audit event
        └─ 7. Destroy connection and delete local files
```

> **Queue note (open item, §17):** `DATABASE.md` §6.5 allows job queues `ingest | analysis | generate | light`. The SQL pool is therefore deployed as a **dedicated worker pool consuming the `analysis` queue family with routing key `sql`**. If a distinct `sql` queue is preferred, it requires a migration of `ck_jobs__queue` and an ADR.

## 3.3 Two execution modes

| Mode | Trigger | Source of SQL | Trust level |
|---|---|---|---|
| **Template mode** | Pipeline stage `SQL_ANALYSIS` (metric production) and the "question library" | Repository-owned templates (§9–10) | Trusted text, **still passed through the same validator** (defense in depth + lint) |
| **Interactive mode** | `POST /projects/{id}/sql/execute` with `sql` | User (or AI, P2) | **Untrusted**: full validation + sandbox |

Both modes use the **same engine configuration, relations, limits, and audit path**. Template mode never gets extra privileges.

---

# 4. Sandbox Specification

## 4.1 Connection setup

Executed by trusted code only, in this order (the user's SQL never runs before step 4):

```python
import duckdb

con = duckdb.connect(database=":memory:", config={
    "threads": cfg.sql_threads,                 # default 2
    "memory_limit": cfg.sql_memory_limit,       # default "2GB"
    "max_temp_directory_size": "0",             # no spilling to disk by default (see §4.3)
    "autoinstall_known_extensions": False,
    "autoload_known_extensions": False,
    "enable_external_access": False,            # applied AFTER views are created (see below)
})
```

Because base relations are **views over the version's Parquet file(s)**, the setup order matters:

1. Connect with default access; `CREATE VIEW` the base relations (§5) over the local, hash-verified Parquet path(s).
2. Set `allowed_paths` to **exactly** those local Parquet files, set `enable_external_access = false`, then `SET lock_configuration = true`.
3. From this point the session can read only the pre-registered files through the pre-built views; it cannot read any other path, open URLs, install/load extensions, attach databases, or change settings.

> **Conformance requirement:** the exact DuckDB setting names and the behavior "views over allow-listed Parquet keep working after external access is disabled" must be **verified against the pinned DuckDB version** by the *sandbox conformance test suite* (§15.4). If the pinned version cannot satisfy this, the fallback is to materialize the base relations into in-memory tables during setup (bounded by `memory_limit`) before disabling external access. The *behavioral* requirements in §4.2 are mandatory regardless of mechanism.

## 4.2 Mandatory behaviors (mechanism-independent)

| # | Requirement |
|---|---|
| S1 | Read-only: no statement can create, modify, or drop persistent objects or data |
| S2 | No filesystem access beyond the pre-registered dataset files (no `read_csv`, `read_parquet`, `glob`, replacement scans on string literals, `COPY`, `EXPORT`, `ATTACH`) |
| S3 | No network access (no `httpfs`, no extension install/load, no secrets) |
| S4 | Session configuration is immutable after setup (`SET`, `PRAGMA`, `RESET` blocked at engine level, not only by the validator) |
| S5 | Only allow-listed relations are visible in the catalog; internal catalog/system functions are not callable |
| S6 | Hard limits: memory, CPU threads, wall-clock timeout, result rows, SQL length, AST complexity |
| S7 | Process isolation: worker has no Postgres credentials, no cloud credentials except object-storage read for the specific key, and no outbound network except that endpoint |
| S8 | Ephemeral storage: working files are in a per-query private directory deleted after execution (success or failure) |
| S9 | One query per connection; connections are never reused across users or queries |
| S10 | Cancellation: `con.interrupt()` on user cancel or timeout; the connection is then destroyed |

## 4.3 Resource limits (defaults, configurable)

| Limit | Default | Behavior on breach |
|---|---|---|
| Statement timeout | 30 s (template mode: 120 s) | `SQL_TIMEOUT` (status `TIMED_OUT`) |
| Memory | 2 GB per query | `SQL_EXECUTION_ERROR` (`resource_limit`) |
| Threads | 2 per query | Throttled |
| Result rows (stored) | 10,000 | Truncated; `truncated: true`; row count reports `10000` with `total_exceeds_cap: true` |
| Rows per result page | 200 | Paginated reads |
| SQL text length | 20,000 chars | `SQL_REJECTED` (`too_long`) |
| AST depth | 40 | `SQL_REJECTED` (`too_complex`) |
| Joins per statement | 8 | `SQL_REJECTED` (`too_complex`) |
| CTEs per statement | 12 | `SQL_REJECTED` (`too_complex`) |
| Subquery nesting | 6 | `SQL_REJECTED` (`too_complex`) |
| Concurrent interactive queries per user | 3 | `RATE_LIMITED` |
| Temp spill | Disabled (`max_temp_directory_size = 0`) | Queries needing spill fail with `resource_limit`; may be raised per deployment after a security review |

---

# 5. Relations Exposed to SQL

The allow-list is **exactly** the relations below. Anything else is `unknown_relation`. All relations are built per **dataset version** by trusted setup code from the Parquet snapshot and the **validated semantic mapping** for that version.

> Column names in `transactions` are the **canonical role names** (lower-case). Columns whose role is not mapped are **absent** from the relation (never `NULL`-filled). A template's `requires` list determines availability (§9.1).

## 5.1 `transactions` — line-level fact (grain: one row per source row)

| Column | Type | Source role | Notes |
|---|---|---|---|
| `transaction_id` | `VARCHAR` | `TRANSACTION_ID` | Order identifier; may repeat across lines of one order |
| `customer_id` | `VARCHAR` | `CUSTOMER_ID` | |
| `product_id` | `VARCHAR` | `PRODUCT_ID` | |
| `product_name` | `VARCHAR` | `PRODUCT_NAME` | |
| `category` | `VARCHAR` | `CATEGORY` | Normalized text (cleaning log records normalization) |
| `quantity` | `DECIMAL(38,10)` | `QUANTITY` | Integer-valued data still stored as decimal for exact sums |
| `price` | `DECIMAL(38,10)` | `PRICE` | Unit price |
| `revenue` | `DECIMAL(38,10)` | `REVENUE`, or derived | If `REVENUE` is unmapped but `PRICE` and `QUANTITY` exist, `revenue = price * quantity` **and** the version's relation metadata sets `revenue_is_derived = true` (surfaced in evidence and report limitations) |
| `discount` | `DECIMAL(38,10)` | `DISCOUNT` | **Percentage in [0, 100]** after standardization (§5.8). If the format cannot be determined, the column is **not exposed** and Discount modules are unavailable |
| `purchase_date` | `DATE` | `PURCHASE_DATE` | UTC-normalized calendar date (PRD §113) |
| `purchase_ts` | `TIMESTAMP` | `PURCHASE_DATE` | Present only if the source has a time component |
| `customer_age` | `INTEGER` | `CUSTOMER_AGE` | |
| `gender` | `VARCHAR` | `GENDER` | |
| `city` / `state` / `country` | `VARCHAR` | `CITY` / `STATE` / `COUNTRY` | |
| `payment_method` | `VARCHAR` | `PAYMENT_METHOD` | Normalized text |

Row-level filtering: none. `transactions` is the cleaned version as stored. (Excluded/flagged records are handled by cleaning, which creates a new version — SQL never silently drops rows.)

## 5.2 `orders` — order-level (grain: one row per `transaction_id`)

```sql
CREATE VIEW orders AS
SELECT
  transaction_id,
  MIN(customer_id)      AS customer_id,      -- deterministic if an order has inconsistent customers (quality flags it)
  MIN(purchase_date)    AS order_date,
  SUM(revenue)          AS order_revenue,
  SUM(quantity)         AS order_quantity,
  COUNT(*)              AS line_count
FROM transactions
WHERE transaction_id IS NOT NULL
GROUP BY transaction_id;
```
Built only when `TRANSACTION_ID` and `REVENUE` (or derivable revenue) are available. Optional columns (`customer_id`, `order_date`, `order_quantity`) appear only when their roles exist. Rows with a `NULL` `transaction_id` are excluded from `orders` and counted in the version's quality report.

## 5.3 `customers` — customer-level (grain: one row per `customer_id`)

```sql
CREATE VIEW customers AS
SELECT
  customer_id,
  MIN(purchase_date)                                   AS first_purchase_date,
  MAX(purchase_date)                                   AS last_purchase_date,
  COUNT(DISTINCT transaction_id)                       AS order_count,        -- falls back to COUNT(*) if TRANSACTION_ID unmapped (frequency_basis = 'ROWS')
  SUM(revenue)                                         AS total_revenue,
  SUM(quantity)                                        AS total_quantity
FROM transactions
WHERE customer_id IS NOT NULL
GROUP BY customer_id;
```
When `TRANSACTION_ID` is unmapped, `order_count` is the **row count** and the relation metadata sets `frequency_basis = 'ROWS'` (surfaced wherever frequency is shown; Orders/AOV remain unavailable).

## 5.4 `products` — product-level (grain: one row per product)

```sql
CREATE VIEW products AS
SELECT
  COALESCE(product_id, product_name)   AS product_key,   -- product_id preferred; falls back to product_name
  MIN(product_name)                    AS product_name,
  MIN(category)                        AS category,
  SUM(revenue)                         AS total_revenue,
  SUM(quantity)                        AS total_quantity,
  COUNT(DISTINCT transaction_id)       AS order_count
FROM transactions
WHERE COALESCE(product_id, product_name) IS NOT NULL
GROUP BY COALESCE(product_id, product_name);
```
(Column omissions follow role availability; `order_count` requires `TRANSACTION_ID`.)

## 5.5 `calendar` — day-level date dimension (grain: one row per calendar day in the data's range)

Built by trusted setup from `MIN(purchase_date)` to `MAX(purchase_date)` (inclusive) with `generate_series`. Interactive SQL **cannot** call `generate_series`; it reads this relation.

| Column | Type | Definition |
|---|---|---|
| `date` | `DATE` | The day |
| `year`, `quarter`, `month` | `INTEGER` | Calendar parts |
| `month_start`, `month_end` | `DATE` | First / last day of the month |
| `week_start` | `DATE` | ISO week start (Monday) |
| `day_of_week` | `INTEGER` | 1 = Monday … 7 = Sunday |
| `is_weekend` | `BOOLEAN` | Saturday/Sunday |
| `month_is_complete` | `BOOLEAN` | `data_min <= month_start AND data_max >= month_end` |
| `week_is_complete` | `BOOLEAN` | `data_min <= week_start AND data_max >= week_start + 6` |
| `year_is_complete` | `BOOLEAN` | `data_min <= Jan 1 AND data_max >= Dec 31` |

**Completeness flags** implement PRD §45 ("Metrics should only be calculated where the required time period is meaningful"): growth metrics compare only **complete** periods.

## 5.6 `run_params` — single-row analysis parameters

| Column | Type | Meaning |
|---|---|---|
| `reference_date` | `DATE` | RFM reference date: `MAX(purchase_date) + 1 day` unless configured |
| `data_min_date`, `data_max_date` | `DATE` | Range of `purchase_date` |
| `currency` | `VARCHAR` | ISO 4217 (project metadata, PRD §112) |
| `rfm_min_customers` | `INTEGER` | Minimum customers for RFM (default `20`; authoritative in `ANALYTICS_SPEC.md`) |
| `revenue_is_derived` | `BOOLEAN` | Whether `transactions.revenue` is `price × quantity` |
| `frequency_basis` | `VARCHAR` | `'ORDERS'` or `'ROWS'` |

## 5.7 `customer_rfm` and `customer_segments` — derived customer relations

Requires roles `CUSTOMER_ID`, `PURCHASE_DATE`, and revenue; and `COUNT(customers) >= rfm_min_customers`.

```sql
CREATE VIEW customer_rfm AS
WITH base AS (
  SELECT
    c.customer_id,
    date_diff('day', c.last_purchase_date, p.reference_date) AS recency_days,
    c.order_count                                            AS frequency,
    c.total_revenue                                          AS monetary
  FROM customers c CROSS JOIN run_params p
),
scored AS (
  SELECT
    *,
    6 - NTILE(5) OVER (ORDER BY recency_days ASC,  customer_id) AS r_score,   -- most recent customers → 5
        NTILE(5) OVER (ORDER BY frequency    ASC,  customer_id) AS f_score,   -- most frequent       → 5
        NTILE(5) OVER (ORDER BY monetary     ASC,  customer_id) AS m_score    -- highest spend       → 5
  FROM base
)
SELECT
  customer_id, recency_days, frequency, monetary,
  r_score, f_score, m_score,
  CAST(r_score AS VARCHAR) || CAST(f_score AS VARCHAR) || CAST(m_score AS VARCHAR) AS rfm_score   -- e.g. '555'
FROM scored;
```

Notes:
- **Scoring is rank-based quintiles via `NTILE(5)` with a deterministic tie-breaker (`customer_id`)** so results are reproducible. Customers with identical values may land in adjacent quintiles; this is documented behavior (ties broken by ID), not an error. `ANALYTICS_SPEC.md` may specify an alternative tie policy; if so, this view is the single place to change it.
- `rfm_score` is the three-digit string (PRD §40 example `555`).

```sql
CREATE VIEW customer_segments AS
SELECT
  customer_id,
  CASE
    WHEN r_score <= 2 AND f_score >= 3                  THEN 'AT_RISK'
    WHEN f_score >= 4 AND m_score >= 4                  THEN 'HIGH_VALUE'
    WHEN f_score >= 3 OR  m_score >= 3                  THEN 'REGULAR'
    ELSE                                                     'OCCASIONAL'
  END AS segment
FROM customer_rfm;
```

Segmentation rules (PRD §39) — **rule-based classifications, not objective truths**:

| Precedence | Segment | Rule (defaults; authoritative in `ANALYTICS_SPEC.md`, versioned as `segmentation_rules_version`) |
|---|---|---|
| 1 | At Risk | Low recency score (`r ≤ 2`) **and** previously engaged (`f ≥ 3`) |
| 2 | High Value | High frequency **and** high monetary (`f ≥ 4` and `m ≥ 4`) |
| 3 | Regular | Moderate engagement (`f ≥ 3` or `m ≥ 3`) |
| 4 | Occasional | Everything else |

Every customer falls into **exactly one** segment (first matching rule wins), so segment counts sum to total customers (a property test, §15.3). Changing a rule changes `segmentation_rules_version` and `PIPELINE_VERSION`.

## 5.8 Discount standardization contract

`transactions.discount` is exposed **only** when the platform can determine its meaning during ingest/cleaning (`STANDARDIZE_NUMERICS`, recorded in the cleaning log):

| Observed values | Interpretation | Stored as |
|---|---|---|
| All within `[0, 1]` and a ratio column name/pattern | Fraction | `× 100` → percent |
| Within `[0, 100]` | Percent | unchanged |
| Otherwise (e.g., currency amounts) | **Undetermined** | column **not exposed**; `DISCOUNT` module `UNAVAILABLE` with reason "Discount format could not be determined." |

Margin analysis is **unavailable in V1**: no cost/margin semantic role exists (PRD §23); the Discount template set reports "Margin if available" as `UNAVAILABLE` (PRD §42).

## 5.9 Relation metadata and schema endpoint

`GET /dataset-versions/{id}/sql/schema` (API_SPEC §7.5/§14) returns exactly the relations and columns exposed for that version, including derived flags — used for editor autocomplete and docs:

```json
{
  "dataset_version_id": "…",
  "relations": [
    {
      "name": "transactions",
      "grain": "one row per source row",
      "row_count": 125106,
      "columns": [
        { "name": "revenue", "type": "DECIMAL(38,10)", "role": "REVENUE", "derived": false },
        { "name": "purchase_date", "type": "DATE", "role": "PURCHASE_DATE" }
      ]
    },
    { "name": "orders", "grain": "one row per transaction_id", "available": true },
    { "name": "customer_rfm", "available": false, "reason": "A customer identifier and purchase date are required." }
  ],
  "run_params": { "reference_date": "2026-09-30", "currency": "INR", "revenue_is_derived": false, "frequency_basis": "ORDERS" }
}
```

---

# 6. SQL Conventions

| Topic | Convention |
|---|---|
| **Dialect** | DuckDB SQL |
| **Statements** | Exactly one `SELECT` (optionally with CTEs / set operations) |
| **Case & quoting** | Lower-case snake_case identifiers; quote only when necessary; no schema/catalog qualifiers (`main.`, `memory.` rejected) |
| **Column lists** | Explicit columns; `SELECT *` is permitted in interactive mode but never in templates |
| **Aliases** | Every output expression has an explicit alias; template output column names are part of the contract |
| **Order** | Every template that returns multiple rows has a **total, deterministic `ORDER BY`** (including a unique tie-breaker) |
| **NULLs** | Sums over empty sets yield `NULL`, not `0`, except where a template explicitly uses `COALESCE`; division uses `NULLIF(denominator, 0)` |
| **Ratios** | Returned as fractions in `[0, 1]` (unit `ratio`); presentation layer multiplies by 100 for `%` display |
| **Money** | `DECIMAL(38,10)` sums; ratios/means computed in `DOUBLE` and stored in metrics rounded to 10 decimal places |
| **Dates** | `DATE` for day-level logic; `date_trunc` for grain; no local-time functions |
| **Parameters** | Named `$param` bound parameters only; never string interpolation (§8) |
| **Determinism** | No `random`, `uuid`, `now`, `current_date`, `current_timestamp`, `today`, `getenv`, or other environment-dependent functions (§7.4) |
| **Window functions** | Always specify total ordering (`ORDER BY …, tie_breaker`) |
| **Top-N** | `ORDER BY metric DESC, key ASC LIMIT $limit` — never rely on arbitrary tie order |

---

# 7. Validation Pipeline

Every statement — template or interactive — passes through the validator **before** the engine sees it. Validation is implemented with `sqlglot` (parse + AST inspection) in `analytics_engine/sqlgen/validator.py` and is also used by `POST /sql/validate` (advisory) and the template linter (CI).

## 7.1 Steps

```text
raw text
  1. Length / encoding check          (≤ 20,000 chars; valid UTF-8; no NUL/control chars)
  2. Parse (sqlglot, duckdb)          → exactly ONE statement, else multiple_statements / parse_error
  3. Root-node check                  → Select | Union/Intersect/Except of Selects (with optional CTEs), else not_select
  4. Forbidden-node scan              → no DDL/DML/Command/Pragma/Set/Copy/Attach/Install/Load/Call/Export/Describe/Show/…
  5. Relation check                   → every table reference ∈ allow-list ∪ query CTE names; no catalog/schema qualifiers;
                                        no string-literal table sources ('file.csv'); no table functions except allow-listed
  6. Function check                   → every function ∈ allow-list; no non-deterministic functions
  7. Complexity check                 → AST depth, joins, CTEs, subquery nesting within limits
  8. Parameter check                  → every $param declared & typed (templates) / only bound params, no ? positional (interactive)
  9. Canonicalization                 → regenerate SQL text from the validated AST (comments/whitespace/quirks removed)
 10. Result wrapping                  → wrap as SELECT * FROM (<canonical>) LIMIT cap+1 for truncation detection
```

**Only the canonical SQL (step 9) executes.** The raw text is stored in `sql_queries.sql_text` for display and audit; the canonical form is stored in `sql_queries.parameters._canonical_sql` (diagnostic, not user-visible by default).

## 7.2 Rejection reasons (`details[].issue` in `SQL_REJECTED`)

| Issue code | Meaning |
|---|---|
| `too_long` | Exceeds length limit |
| `invalid_encoding` | Non-UTF-8 / control characters |
| `parse_error` | Not valid DuckDB SQL (message sanitized; position included) |
| `empty_statement` | Nothing to execute |
| `multiple_statements` | More than one statement (`;`-separated or otherwise) |
| `not_select` | Root is not a query (e.g., `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`, `TRUNCATE`) |
| `forbidden_statement` | `PRAGMA`, `SET`, `RESET`, `COPY`, `EXPORT`, `IMPORT`, `ATTACH`, `DETACH`, `INSTALL`, `LOAD`, `CALL`, `DESCRIBE`, `SHOW`, `EXPLAIN`, `USE`, `VACUUM`, `CHECKPOINT`, `BEGIN/COMMIT/ROLLBACK` … |
| `forbidden_keyword` | A forbidden construct found nested (e.g., `SELECT … INTO`, data-modifying CTE) — includes the PRD §48 list `DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE` |
| `unknown_relation` | Table not in the allow-list (includes `information_schema`, `pg_catalog`, `duckdb_*`, `sqlite_*`) |
| `qualified_name_not_allowed` | `catalog.schema.table` qualification used |
| `literal_table_source` | `FROM 'path'` / replacement scan |
| `forbidden_function` | Function not in the allow-list (e.g., `read_csv`, `read_parquet`, `glob`, `getenv`, `current_setting`, `query`, `query_table`, `duckdb_*`, `pragma_*`, `parquet_*`, `which_secret`) |
| `nondeterministic_function` | `random`, `uuid`, `now`, `current_date`, `current_timestamp`, `today`, … (breaks reproducibility, PRD §5.4) |
| `too_complex` | Depth/joins/CTEs/subquery limits exceeded |
| `parameter_error` | Undeclared, mistyped, or positional parameter |

`POST /sql/validate` returns the same issue codes with positions (API_SPEC §7.12).

## 7.3 Allow-listed relations

```text
transactions · orders · customers · products · calendar · run_params · customer_rfm · customer_segments
```
(Availability per version, §5.9. Referencing a relation that exists in the allow-list but is **unavailable** for the version returns `SQL_REJECTED` with `unknown_relation` and `meta.reason` explaining the missing role — consistent with the "Unavailable" UX.)

## 7.4 Allow-listed functions (non-exhaustive categories; the exact list lives in `sqlgen/allowlist.py` and is tested)

| Category | Allowed |
|---|---|
| Aggregates | `count, sum, avg, min, max, median, mode, stddev, stddev_pop, stddev_samp, variance, var_pop, var_samp, corr, covar_pop, covar_samp, quantile_cont, quantile_disc, approx_count_distinct, arg_min, arg_max, any_value, first, last, list, string_agg, bool_and, bool_or, count_if, histogram` (subject to pinned DuckDB support) |
| Window | `row_number, rank, dense_rank, percent_rank, cume_dist, ntile, lag, lead, first_value, last_value, nth_value` |
| Math | `abs, ceil, floor, round, trunc, sqrt, power, pow, ln, log, log10, exp, sign, greatest, least, mod` |
| Null handling | `coalesce, nullif, ifnull` |
| String | `lower, upper, trim, ltrim, rtrim, length, substr, substring, replace, concat, concat_ws, contains, starts_with, ends_with, regexp_matches, regexp_replace, split_part, left, right, lpad, rpad` |
| Date/time (pure) | `date_trunc, date_part, date_diff, date_add, date_sub, year, quarter, month, week, day, dayofweek, isodow, strftime, strptime, make_date, last_day, epoch` |
| Cast / conditional | `CAST`, `TRY_CAST`, `CASE`, `IF/IIF` |
| Table functions | `unnest` only |

Denied explicitly (non-exhaustive): `read_*`, `glob`, `parquet_*`, `sniff_csv`, `query`, `query_table`, `duckdb_*`, `pragma_*`, `current_setting`, `getenv`, `which_secret`, `list_secrets`, `generate_series`, `range` (resource amplification; available only inside trusted setup), `random`, `uuid`, `gen_random_uuid`, `now`, `current_*`, `today`, `getvariable`, `typeof` on catalog objects, any `*_scan` function.

## 7.5 Implementation sketch (validator core)

```python
from sqlglot import parse, exp

FORBIDDEN_ROOTS = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter,
                   exp.Command, exp.Pragma, exp.Set, exp.Copy, exp.Attach, exp.Detach,
                   exp.Use, exp.Transaction, exp.Commit, exp.Rollback, exp.Describe, exp.Show)

def validate(sql: str, allowed_relations: set[str], limits: Limits) -> ValidatedQuery:
    if len(sql) > limits.max_chars: raise Reject("too_long")
    try:
        stmts = [s for s in parse(sql, read="duckdb") if s is not None]
    except Exception as e:
        raise Reject("parse_error", meta=sanitize(e))
    if not stmts: raise Reject("empty_statement")
    if len(stmts) > 1: raise Reject("multiple_statements")
    tree = stmts[0]

    root = tree.this if isinstance(tree, exp.Subquery) else tree
    if not isinstance(root, (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.With)):
        raise Reject("not_select")

    for node in tree.walk():
        if isinstance(node, FORBIDDEN_ROOTS):        raise Reject("forbidden_keyword", keyword=type(node).__name__)
        if isinstance(node, exp.Into):               raise Reject("forbidden_keyword", keyword="INTO")
        if isinstance(node, exp.Table):
            if node.args.get("db") or node.args.get("catalog"): raise Reject("qualified_name_not_allowed")
            if not isinstance(node.this, exp.Identifier):       raise Reject("literal_table_source")
            name = node.name.lower()
            if name not in allowed_relations and name not in cte_names(tree):
                raise Reject("unknown_relation", relation=name)
        if isinstance(node, (exp.Anonymous, exp.Func)):
            fname = function_name(node).lower()
            if fname in NONDETERMINISTIC: raise Reject("nondeterministic_function", function=fname)
            if fname not in ALLOWED_FUNCTIONS: raise Reject("forbidden_function", function=fname)
        if isinstance(node, exp.TableFromRows) or is_table_function(node):
            if function_name(node).lower() not in ALLOWED_TABLE_FUNCTIONS: raise Reject("forbidden_function")

    enforce_complexity(tree, limits)
    check_parameters(tree)
    canonical = tree.sql(dialect="duckdb")           # executed text
    return ValidatedQuery(canonical=canonical, ast=tree)
```

*(Illustrative — the real implementation must be driven by the adversarial corpus in §15.2; node class names vary by `sqlglot` version and are pinned by tests.)*

---

# 8. Parameters and Injection Safety

- Templates declare parameters in the registry (§9.1) with **type, bounds, default, and allowed values**. Example: `limit: INTEGER, min=1, max=100, default=10`.
- Parameters are bound through DuckDB prepared statements (`$name`). **No parameter value is ever concatenated into SQL text.**
- Interactive SQL may use bound parameters only if provided in `parameters`; positional `?` markers are rejected. Literals in the SQL text are allowed (they are part of the validated AST).
- Identifier parameters (column or table names) are **not supported**. Where a template varies by column (e.g., geography level), the registry defines **separate templates** (`geo_revenue_by_country`, `geo_revenue_by_state`, `geo_revenue_by_city`) rather than interpolating identifiers.
- Template construction for optional roles (e.g., which geography columns exist) happens in the **trusted template builder** by selecting among pre-written variants — not by string-formatting user input.

---

# 9. Query Template Registry

## 9.1 Template definition

Templates are declared in the domain plugin (`domains/retail/sql/templates/*.yaml`) and loaded into the registry. Schema:

```yaml
key: sales_total_revenue                 # stable identifier (never reused)
version: 1                               # increments on any SQL/column change (bumps PIPELINE_VERSION)
domain: retail
category: Sales                          # Sales | Customers | Products | Categories | Time | Geography | Loyalty | Purchase behavior
title: Total revenue
question: What is the total revenue?     # shown as "Question" in the SQL explorer (PRD §47)
requires:
  roles: [REVENUE]                       # semantic roles that must be mapped (or derivable)
  relations: [transactions]
  min_rows: 1
parameters: []                           # [{name, type, min, max, default, allowed}]
output:
  - {name: total_revenue, type: DECIMAL, unit: currency}
sql: |
  SELECT SUM(revenue) AS total_revenue FROM transactions;
metric_bindings:
  - {metric_name: total_revenue, module: SALES, value_column: total_revenue,
     calculation: "SUM(revenue)", dimensions: []}
chart:                                   # optional suggestion (selection map: DESIGN §4.17)
  type: CARD
availability_reason_when_missing: "A revenue column (or price and quantity) is required."
```

## 9.2 Availability and "Unavailable" behavior

Template availability is **computed deterministically** from the validated mapping (and relation availability):

- All `requires.roles` present (revenue counts as present when derivable from `PRICE × QUANTITY`) **and** `min_rows` satisfied → `AVAILABLE`.
- Otherwise → `UNAVAILABLE` with `reason` (the template's message, plus `missing_roles`). It is persisted into `module_availability`, shown in the UI, and the template is **not executed**.
- A template that errors at execution is `FAILED` (retryable per stage rules); it is **never** replaced by a guess.

`GET /analysis-runs/{id}/sql/questions` returns templates grouped by category with `availability`, `sql_text`, `parameters`, and `chart_suggestion` (API_SPEC §7.12).

## 9.3 Naming and ordering rules (lint-enforced)

- `key` is `snake_case`, prefixed by area: `sales_`, `cust_`, `prod_`, `cat_`, `time_`, `geo_`, `loy_`, `beh_`, `disc_`, `pay_`.
- Every multi-row template ends with a total `ORDER BY`.
- No `SELECT *`; every output column aliased; declared `output` equals the actual projection (checked by executing against the golden dataset in CI).
- Only allow-listed relations/functions; parameters declared; no non-deterministic functions (validator runs on every template in CI).

---

# 10. Template Library (Retail V1)

> All queries below are **reference implementations** for `domains/retail`. They are written for the full-role case; the registry applies the `requires` gates and uses the pre-written variants noted. Ratios are fractions in `[0, 1]`. `$limit` etc. are bound parameters.

## 10.1 Sales (PRD §37)

| Key | Requires roles | Purpose |
|---|---|---|
| `sales_total_revenue` | `REVENUE` | Total revenue |
| `sales_total_orders` | `TRANSACTION_ID` | Total orders |
| `sales_total_quantity` | `QUANTITY` | Total quantity |
| `sales_average_order_value` | `TRANSACTION_ID`, `REVENUE` | AOV |
| `sales_avg_revenue_per_customer` | `CUSTOMER_ID`, `REVENUE` | Average revenue per customer |
| `sales_growth_latest_period` | `PURCHASE_DATE`, `REVENUE` (+`TRANSACTION_ID` for orders) | Revenue & order growth, latest vs previous **complete** month |

```sql
-- sales_total_revenue
SELECT SUM(revenue) AS total_revenue
FROM transactions;

-- sales_total_orders
SELECT COUNT(DISTINCT transaction_id) AS total_orders
FROM transactions;

-- sales_total_quantity
SELECT SUM(quantity) AS total_quantity
FROM transactions;

-- sales_average_order_value
SELECT SUM(order_revenue) / NULLIF(COUNT(*), 0) AS average_order_value
FROM orders;

-- sales_avg_revenue_per_customer
SELECT SUM(total_revenue) / NULLIF(COUNT(*), 0) AS avg_revenue_per_customer
FROM customers;

-- sales_growth_latest_period  (latest complete month vs the immediately preceding complete month)
WITH months AS (
  SELECT DISTINCT month_start, month_is_complete FROM calendar
),
monthly AS (
  SELECT m.month_start,
         COALESCE(SUM(t.revenue), 0)                 AS revenue,
         COUNT(DISTINCT t.transaction_id)            AS orders
  FROM months m
  LEFT JOIN transactions t
         ON CAST(date_trunc('month', t.purchase_date) AS DATE) = m.month_start
  WHERE m.month_is_complete
  GROUP BY m.month_start
),
ranked AS (
  SELECT *, ROW_NUMBER() OVER (ORDER BY month_start DESC) AS rn FROM monthly
)
SELECT
  cur.month_start                                              AS current_month,
  prv.month_start                                              AS previous_month,
  cur.revenue                                                  AS current_revenue,
  prv.revenue                                                  AS previous_revenue,
  (cur.revenue - prv.revenue) / NULLIF(prv.revenue, 0)         AS revenue_growth,
  (cur.orders  - prv.orders)  / NULLIF(prv.orders,  0)         AS order_growth
FROM ranked cur
JOIN ranked prv
  ON cur.rn = 1 AND prv.rn = 2
 AND prv.month_start = CAST(cur.month_start - INTERVAL 1 MONTH AS DATE);   -- consecutive months only
```
If fewer than two consecutive complete months exist, the query returns **no rows** → growth metrics are `UNAVAILABLE` with reason "Fewer than two consecutive complete months of data." (never `0`).

## 10.2 Customers (PRD §38)

| Key | Requires | Purpose |
|---|---|---|
| `cust_total_customers` | `CUSTOMER_ID` | Total customers |
| `cust_new_vs_returning_monthly` | `CUSTOMER_ID`, `PURCHASE_DATE` | New vs returning per complete month |
| `cust_repeat_purchase_rate` | `CUSTOMER_ID` (+`TRANSACTION_ID` for order basis) | Share of customers with ≥ 2 orders |
| `cust_avg_customer_revenue` | `CUSTOMER_ID`, `REVENUE` | Average revenue per customer |
| `cust_avg_orders_per_customer` | `CUSTOMER_ID` (+`TRANSACTION_ID`) | Average orders per customer |
| `cust_top_customers` | `CUSTOMER_ID`, `REVENUE` | Top customers by revenue |
| `cust_revenue_deciles` | `CUSTOMER_ID`, `REVENUE` | Revenue concentration by customer decile (Pareto) |
| `cust_segment_summary` | `CUSTOMER_ID`, `PURCHASE_DATE`, `REVENUE` | Segment table (PRD §39, §50 example) |
| `cust_rfm_table` | same | Customer-level RFM (paginated reads) |
| `cust_rfm_distribution` | same | Customers by R and F score (heatmap source) |

```sql
-- cust_total_customers
SELECT COUNT(*) AS total_customers FROM customers;

-- cust_new_vs_returning_monthly
-- "New" = first purchase falls in the month; "Returning" = first purchase before the month.
-- The dataset's first month overstates "new" (history before the dataset start is unknown): the engine excludes
-- the first month from headline KPIs and annotates the series.
SELECT
  c.month_start,
  COUNT(DISTINCT CASE WHEN cu.first_purchase_date >= c.month_start THEN t.customer_id END) AS new_customers,
  COUNT(DISTINCT CASE WHEN cu.first_purchase_date <  c.month_start THEN t.customer_id END) AS returning_customers
FROM transactions t
JOIN calendar  c  ON c.date = t.purchase_date
JOIN customers cu ON cu.customer_id = t.customer_id
WHERE c.month_is_complete
GROUP BY c.month_start
ORDER BY c.month_start;

-- cust_repeat_purchase_rate
SELECT
  COUNT(*) FILTER (WHERE order_count >= 2) / NULLIF(COUNT(*), 0) AS repeat_purchase_rate,
  COUNT(*) FILTER (WHERE order_count >= 2)                       AS repeat_customers,
  COUNT(*)                                                       AS total_customers
FROM customers;

-- cust_avg_customer_revenue
SELECT AVG(total_revenue) AS avg_customer_revenue FROM customers;

-- cust_avg_orders_per_customer
SELECT AVG(order_count) AS avg_orders_per_customer FROM customers;

-- cust_top_customers   (params: $limit INTEGER 1..100 default 10)
SELECT customer_id, total_revenue, order_count, first_purchase_date, last_purchase_date
FROM customers
ORDER BY total_revenue DESC, customer_id ASC
LIMIT $limit;

-- cust_revenue_deciles
WITH ranked AS (
  SELECT customer_id, total_revenue,
         NTILE(10) OVER (ORDER BY total_revenue DESC, customer_id ASC) AS decile
  FROM customers
)
SELECT
  decile,
  COUNT(*)                                                    AS customers,
  SUM(total_revenue)                                          AS revenue,
  SUM(total_revenue) / NULLIF(SUM(SUM(total_revenue)) OVER (), 0) AS revenue_share
FROM ranked
GROUP BY decile
ORDER BY decile;

-- cust_segment_summary    (reproduces the PRD §50 example: revenue share vs customer share)
SELECT
  s.segment,
  COUNT(*)                                                                  AS customers,
  COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0)                               AS customer_share,
  SUM(c.total_revenue)                                                      AS revenue,
  SUM(c.total_revenue) / NULLIF(SUM(SUM(c.total_revenue)) OVER (), 0)       AS revenue_share,
  SUM(c.total_revenue) / NULLIF(SUM(c.order_count), 0)                      AS average_order_value
FROM customer_segments s
JOIN customers c USING (customer_id)
GROUP BY s.segment
ORDER BY CASE s.segment WHEN 'HIGH_VALUE' THEN 1 WHEN 'REGULAR' THEN 2 WHEN 'OCCASIONAL' THEN 3 ELSE 4 END;

-- cust_rfm_table   (read through paginated result API; params: none; deterministic order)
SELECT customer_id, recency_days, frequency, monetary, r_score, f_score, m_score, rfm_score
FROM customer_rfm
ORDER BY monetary DESC, customer_id ASC;

-- cust_rfm_distribution
SELECT r_score, f_score, COUNT(*) AS customers, SUM(monetary) AS revenue
FROM customer_rfm
GROUP BY r_score, f_score
ORDER BY r_score DESC, f_score DESC;
```

`cust_segment_summary`'s `average_order_value` is order-weighted (`revenue / orders`) and requires the order-count basis; if `frequency_basis = 'ROWS'` the column is labeled "Average revenue per transaction row" and the AOV metric is unavailable.

## 10.3 Products (PRD §41)

| Key | Requires | Purpose |
|---|---|---|
| `prod_top_by_revenue` | (`PRODUCT_ID` or `PRODUCT_NAME`), `REVENUE` | Top products by revenue |
| `prod_bottom_by_revenue` | same | Bottom products by revenue |
| `prod_top_by_quantity` | (…), `QUANTITY` | Top by quantity |
| `prod_revenue_and_quantity` | (…) | Product table (paginated) |
| `prod_pareto` | (…), `REVENUE` | Cumulative contribution curve |

```sql
-- prod_top_by_revenue   ($limit INTEGER 1..100 default 10)
SELECT product_key, product_name, category, total_revenue, total_quantity,
       total_revenue / NULLIF(SUM(total_revenue) OVER (), 0) AS revenue_share
FROM products
ORDER BY total_revenue DESC, product_key ASC
LIMIT $limit;

-- prod_bottom_by_revenue   ($limit INTEGER 1..100 default 10)  -- products with at least one sale (all rows in `products` qualify)
SELECT product_key, product_name, category, total_revenue, total_quantity,
       total_revenue / NULLIF(SUM(total_revenue) OVER (), 0) AS revenue_share
FROM products
ORDER BY total_revenue ASC, product_key ASC
LIMIT $limit;

-- prod_top_by_quantity   ($limit)
SELECT product_key, product_name, category, total_quantity, total_revenue
FROM products
ORDER BY total_quantity DESC, product_key ASC
LIMIT $limit;

-- prod_revenue_and_quantity   (paginated read)
SELECT product_key, product_name, category, total_revenue, total_quantity, order_count,
       total_revenue / NULLIF(SUM(total_revenue) OVER (), 0) AS revenue_share
FROM products
ORDER BY total_revenue DESC, product_key ASC;

-- prod_pareto
WITH ranked AS (
  SELECT product_key, total_revenue,
         ROW_NUMBER() OVER (ORDER BY total_revenue DESC, product_key ASC) AS rank
  FROM products
)
SELECT
  rank, product_key, total_revenue,
  SUM(total_revenue) OVER (ORDER BY rank)
    / NULLIF(SUM(total_revenue) OVER (), 0) AS cumulative_revenue_share
FROM ranked
ORDER BY rank;
```
Pareto series returned to the UI is **bucketed to ≤ 1,000 points** by the engine (e.g., every k-th rank plus the top 100) with the bucketing recorded in the chart spec.

## 10.4 Categories (PRD §41)

| Key | Requires | Purpose |
|---|---|---|
| `cat_revenue_quantity_contribution` | `CATEGORY`, `REVENUE` | Revenue, quantity, orders, share by category |

```sql
SELECT
  category,
  SUM(revenue)                                              AS revenue,
  SUM(quantity)                                             AS quantity,
  COUNT(DISTINCT transaction_id)                            AS orders,
  SUM(revenue) / NULLIF(SUM(SUM(revenue)) OVER (), 0)       AS revenue_share
FROM transactions
WHERE category IS NOT NULL
GROUP BY category
ORDER BY revenue DESC, category ASC;
```
Rows with `NULL` category are excluded from this breakdown; the engine records `revenue_unclassified` (the revenue on `NULL`-category rows) as a separate metric so that category totals reconcile with `total_revenue` (property test, §15.3). Dimensional metrics persist top-N (default 20) categories plus an `__OTHER__` bucket.

## 10.5 Time (PRD §45)

| Key | Requires | Purpose |
|---|---|---|
| `time_revenue_daily` | `PURCHASE_DATE`, `REVENUE` | Daily revenue |
| `time_revenue_weekly` | same | Weekly revenue |
| `time_revenue_monthly` | same | Monthly revenue & orders |
| `time_revenue_yearly` | same | Yearly revenue |
| `time_mom_growth` | same (≥ 2 consecutive complete months) | Month-over-month growth series |
| `time_yoy_growth` | same (≥ 13 complete months) | Year-over-year growth series |
| `time_revenue_by_day_of_week` | same | Day-of-week profile |

```sql
-- time_revenue_daily   (days without sales appear with revenue = 0 because the calendar drives the series)
SELECT c.date, COALESCE(SUM(t.revenue), 0) AS revenue, COUNT(DISTINCT t.transaction_id) AS orders
FROM calendar c
LEFT JOIN transactions t ON t.purchase_date = c.date
GROUP BY c.date
ORDER BY c.date;

-- time_revenue_weekly   (complete ISO weeks only; partial edge weeks are excluded and flagged)
SELECT c.week_start, COALESCE(SUM(t.revenue), 0) AS revenue, COUNT(DISTINCT t.transaction_id) AS orders
FROM calendar c
LEFT JOIN transactions t ON t.purchase_date = c.date
WHERE c.week_is_complete
GROUP BY c.week_start
ORDER BY c.week_start;

-- time_revenue_monthly   (partial first/last months are returned with is_complete = false so charts can annotate them;
--                         growth templates use only complete months)
SELECT c.month_start,
       BOOL_AND(c.month_is_complete)               AS is_complete,
       COALESCE(SUM(t.revenue), 0)                 AS revenue,
       COUNT(DISTINCT t.transaction_id)            AS orders
FROM calendar c
LEFT JOIN transactions t ON t.purchase_date = c.date
GROUP BY c.month_start
ORDER BY c.month_start;

-- time_revenue_yearly
SELECT c.year,
       BOOL_AND(c.year_is_complete)                AS is_complete,
       COALESCE(SUM(t.revenue), 0)                 AS revenue,
       COUNT(DISTINCT t.transaction_id)            AS orders
FROM calendar c
LEFT JOIN transactions t ON t.purchase_date = c.date
GROUP BY c.year
ORDER BY c.year;

-- time_mom_growth   (consecutive complete months only)
WITH monthly AS (
  SELECT c.month_start, COALESCE(SUM(t.revenue), 0) AS revenue
  FROM calendar c
  LEFT JOIN transactions t ON t.purchase_date = c.date
  WHERE c.month_is_complete
  GROUP BY c.month_start
)
SELECT cur.month_start, cur.revenue, prv.revenue AS previous_revenue,
       (cur.revenue - prv.revenue) / NULLIF(prv.revenue, 0) AS mom_growth
FROM monthly cur
JOIN monthly prv ON prv.month_start = CAST(cur.month_start - INTERVAL 1 MONTH AS DATE)
ORDER BY cur.month_start;

-- time_yoy_growth   (same month, prior year, both complete)
WITH monthly AS (
  SELECT c.month_start, COALESCE(SUM(t.revenue), 0) AS revenue
  FROM calendar c
  LEFT JOIN transactions t ON t.purchase_date = c.date
  WHERE c.month_is_complete
  GROUP BY c.month_start
)
SELECT cur.month_start, cur.revenue, prv.revenue AS previous_year_revenue,
       (cur.revenue - prv.revenue) / NULLIF(prv.revenue, 0) AS yoy_growth
FROM monthly cur
JOIN monthly prv ON prv.month_start = CAST(cur.month_start - INTERVAL 12 MONTH AS DATE)
ORDER BY cur.month_start;

-- time_revenue_by_day_of_week
SELECT c.day_of_week,
       COALESCE(SUM(t.revenue), 0)                 AS revenue,
       COUNT(DISTINCT t.transaction_id)            AS orders
FROM calendar c
LEFT JOIN transactions t ON t.purchase_date = c.date
GROUP BY c.day_of_week
ORDER BY c.day_of_week;
```
The engine downsamples daily series to ≤ 1,000 points by aggregating to weekly/monthly for display and records the grain (PRD §75).

## 10.6 Geography (PRD §44)

Pre-written variants (no identifier interpolation):

| Key | Requires | Purpose |
|---|---|---|
| `geo_revenue_by_country` | `COUNTRY`, `REVENUE` | Revenue, orders, customers by country |
| `geo_revenue_by_state` | `STATE`, `REVENUE` | By state (with country if mapped — variant `geo_revenue_by_country_state`) |
| `geo_revenue_by_city` | `CITY`, `REVENUE` | By city (with state/country if mapped — variants) |
| `geo_customer_distribution` | `CUSTOMER_ID`, (`COUNTRY` or `STATE` or `CITY`) | Distinct customers by region |

```sql
-- geo_revenue_by_country
SELECT country,
       SUM(revenue)                                       AS revenue,
       COUNT(DISTINCT transaction_id)                     AS orders,
       COUNT(DISTINCT customer_id)                        AS customers,
       SUM(revenue) / NULLIF(SUM(SUM(revenue)) OVER (), 0) AS revenue_share
FROM transactions
WHERE country IS NOT NULL
GROUP BY country
ORDER BY revenue DESC, country ASC;

-- geo_revenue_by_state  (variant when COUNTRY is also mapped: GROUP BY country, state)
SELECT state,
       SUM(revenue)                                       AS revenue,
       COUNT(DISTINCT transaction_id)                     AS orders,
       COUNT(DISTINCT customer_id)                        AS customers,
       SUM(revenue) / NULLIF(SUM(SUM(revenue)) OVER (), 0) AS revenue_share
FROM transactions
WHERE state IS NOT NULL
GROUP BY state
ORDER BY revenue DESC, state ASC;

-- geo_revenue_by_city   (variant: GROUP BY country, state, city when those roles exist, to avoid merging same-named cities)
SELECT city,
       SUM(revenue)                                       AS revenue,
       COUNT(DISTINCT transaction_id)                     AS orders,
       COUNT(DISTINCT customer_id)                        AS customers,
       SUM(revenue) / NULLIF(SUM(SUM(revenue)) OVER (), 0) AS revenue_share
FROM transactions
WHERE city IS NOT NULL
GROUP BY city
ORDER BY revenue DESC, city ASC;
```
Optional `COUNT(DISTINCT …)` columns are omitted when their roles are absent (variant selection in the trusted builder). A map visualization is P2; the API returns tabular series only.

## 10.7 Discount (PRD §42) — association only

| Key | Requires | Purpose |
|---|---|---|
| `disc_band_summary` | `DISCOUNT`, `REVENUE` (+`TRANSACTION_ID`) | Revenue, orders, AOV by discount band |
| `disc_revenue_association` | `DISCOUNT`, `REVENUE` | Pearson association between discount and revenue |

```sql
-- disc_band_summary   (bands in percent; fixed default edges 0 | (0,10] | (10,20] | (20,30] | >30; versioned in the template)
WITH banded AS (
  SELECT
    CASE
      WHEN discount = 0  THEN '0'
      WHEN discount <= 10 THEN '(0,10]'
      WHEN discount <= 20 THEN '(10,20]'
      WHEN discount <= 30 THEN '(20,30]'
      ELSE                     '>30'
    END AS discount_band,
    CASE
      WHEN discount = 0  THEN 1
      WHEN discount <= 10 THEN 2
      WHEN discount <= 20 THEN 3
      WHEN discount <= 30 THEN 4
      ELSE                     5
    END AS band_order,
    revenue, quantity, transaction_id
  FROM transactions
  WHERE discount IS NOT NULL
)
SELECT
  discount_band,
  COUNT(DISTINCT transaction_id)                                       AS orders,
  SUM(revenue)                                                         AS revenue,
  SUM(revenue) / NULLIF(COUNT(DISTINCT transaction_id), 0)             AS average_order_value,  -- see caveat
  SUM(quantity)                                                        AS quantity
FROM banded
GROUP BY discount_band, band_order
ORDER BY band_order;

-- disc_revenue_association
SELECT corr(discount, revenue) AS pearson_discount_revenue,
       COUNT(*)                AS observations
FROM transactions
WHERE discount IS NOT NULL AND revenue IS NOT NULL;
```
**Caveats shown with the results (PRD §42):** (1) discounts are analyzed at **line** level; an order can span bands, so band-level AOV is `band revenue / orders touching the band` and is labeled accordingly; (2) results describe **association, not causation** — responses carry `interpretation: ASSOCIATION_NOT_CAUSATION`; (3) margin is unavailable in V1 (§5.8). Spearman correlation is computed in the Python statistics layer (EDA), not in SQL, because average-rank handling of ties is implemented there (ANALYTICS_SPEC).

## 10.8 Payment (PRD §43)

```sql
-- pay_summary   (requires PAYMENT_METHOD, REVENUE, TRANSACTION_ID)
SELECT
  payment_method,
  COUNT(DISTINCT transaction_id)                                  AS orders,
  SUM(revenue)                                                    AS revenue,
  SUM(revenue) / NULLIF(COUNT(DISTINCT transaction_id), 0)        AS average_order_value,
  SUM(revenue) / NULLIF(SUM(SUM(revenue)) OVER (), 0)             AS revenue_share
FROM transactions
WHERE payment_method IS NOT NULL
GROUP BY payment_method
ORDER BY revenue DESC, payment_method ASC;
```

## 10.9 Purchase behavior (PRD §57 page 4)

| Key | Requires | Purpose |
|---|---|---|
| `beh_order_size_distribution` | `TRANSACTION_ID` (+`QUANTITY`) | Distribution of items per order |
| `beh_order_value_deciles` | `TRANSACTION_ID`, `REVENUE` | Order value by decile (min/median/max per decile) |
| `beh_purchase_frequency` | `CUSTOMER_ID` (+`TRANSACTION_ID`) | Customers by number of orders |
| `beh_basket_summary` | `TRANSACTION_ID`, `QUANTITY` | Average and median basket quantity/lines |

```sql
-- beh_order_size_distribution   (by line count; quantity-based variant uses order_quantity when QUANTITY is mapped)
SELECT
  CASE WHEN line_count >= 10 THEN '10+' ELSE CAST(line_count AS VARCHAR) END AS lines_per_order,
  MIN(line_count)                                                            AS sort_key,
  COUNT(*)                                                                   AS orders
FROM orders
GROUP BY 1
ORDER BY sort_key;

-- beh_order_value_deciles
WITH ranked AS (
  SELECT order_revenue, NTILE(10) OVER (ORDER BY order_revenue ASC, transaction_id ASC) AS decile
  FROM orders
)
SELECT decile, COUNT(*) AS orders,
       MIN(order_revenue) AS min_order_value,
       median(order_revenue) AS median_order_value,
       MAX(order_revenue) AS max_order_value
FROM ranked
GROUP BY decile
ORDER BY decile;

-- beh_purchase_frequency
SELECT
  CASE WHEN order_count >= 5 THEN '5+' ELSE CAST(order_count AS VARCHAR) END AS orders_per_customer,
  MIN(order_count)                                                           AS sort_key,
  COUNT(*)                                                                   AS customers,
  SUM(total_revenue)                                                         AS revenue
FROM customers
GROUP BY 1
ORDER BY sort_key;

-- beh_basket_summary
SELECT AVG(order_quantity) AS avg_basket_quantity,
       median(order_quantity) AS median_basket_quantity,
       AVG(line_count)     AS avg_lines_per_order
FROM orders;
```

## 10.10 Loyalty (PRD §46, §123)

| Key | Requires | Purpose |
|---|---|---|
| `loy_inter_purchase_days` | `CUSTOMER_ID`, `PURCHASE_DATE`, `TRANSACTION_ID` | Average/median days between a customer's consecutive orders |
| `loy_cohort_retention` | `CUSTOMER_ID`, `PURCHASE_DATE` | Monthly cohort activity matrix |
| `loy_at_risk_customers` | RFM requirements | Customers in the At Risk segment (paginated) |

```sql
-- loy_inter_purchase_days
WITH gaps AS (
  SELECT customer_id, order_date,
         date_diff('day',
                   LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date, transaction_id),
                   order_date) AS days_since_previous
  FROM orders
  WHERE customer_id IS NOT NULL
)
SELECT AVG(days_since_previous)    AS avg_days_between_orders,
       median(days_since_previous) AS median_days_between_orders,
       COUNT(*)                    AS observations
FROM gaps
WHERE days_since_previous IS NOT NULL;

-- loy_cohort_retention   (cohort size = active_customers where months_since_first = 0; retention ratio derived by the engine)
WITH cust AS (
  SELECT customer_id, CAST(date_trunc('month', first_purchase_date) AS DATE) AS cohort_month
  FROM customers
),
active AS (
  SELECT DISTINCT customer_id, CAST(date_trunc('month', purchase_date) AS DATE) AS active_month
  FROM transactions
  WHERE customer_id IS NOT NULL
)
SELECT c.cohort_month,
       date_diff('month', c.cohort_month, a.active_month) AS months_since_first,
       COUNT(DISTINCT a.customer_id)                      AS active_customers
FROM cust c
JOIN active a USING (customer_id)
GROUP BY c.cohort_month, months_since_first
ORDER BY c.cohort_month, months_since_first;

-- loy_at_risk_customers   (paginated read)
SELECT r.customer_id, r.recency_days, r.frequency, r.monetary, r.rfm_score
FROM customer_rfm r
JOIN customer_segments s USING (customer_id)
WHERE s.segment = 'AT_RISK'
ORDER BY r.monetary DESC, r.customer_id ASC;
```
Cohort retention for cohorts that include the **partial first month** is annotated; the earliest cohort aggregates "all customers observed in the first month, including pre-existing customers," so the UI labels it accordingly.

## 10.11 Library summary

| Category | Templates | Primary PRD sections |
|---|---|---|
| Sales | 6 | §37 |
| Customers (incl. segmentation & RFM) | 10 | §38–40 |
| Products | 5 | §41 |
| Categories | 1 | §41 |
| Time | 7 | §45 |
| Geography | 4 (+ variants) | §44 |
| Discount | 2 | §42 |
| Payment | 1 | §43 |
| Purchase behavior | 4 | §57 |
| Loyalty | 3 | §46, §123 |

---

# 11. From SQL to Verified Metrics

## 11.1 Flow

```text
Template (registry) ──execute in sandbox──► result rows ──metric_bindings──► metrics rows
          │                                                                     │
          └── sql_queries row (SUCCEEDED, sql_text, duration, dataset_version) ◄─┘ metrics.sql_query_id
```

- The pipeline stage `SQL_ANALYSIS` executes every **available** template once per run in template mode (parallel across a bounded pool), persists one `sql_queries` row per execution (`origin = 'TEMPLATE'`), and writes metrics through the metric registry (`ARCHITECTURE.md` §8.4).
- Each metric stores: `metric_name`, `dimensions`, `value` (exact `DECIMAL`) or `value_series`, `unit`, `currency`, `source` (the relation), `calculation` (the binding's text, e.g., `SUM(revenue)`), `sql_query_id`, `dataset_version_id`, `pipeline_version`, `config_hash` (`DATABASE.md` §6.7).
- **Insights, recommendations, charts, reports, decks, and Power BI measures read these metrics by ID.** They do not execute SQL (PRD §60, §96).

## 11.2 Metric binding rules

| Result shape | Binding | Example |
|---|---|---|
| Single row, scalar column | One metric, `dimensions = {}` | `total_revenue` ← `sales_total_revenue.total_revenue` |
| Multi-row grouped result | One metric per row (top-N + `__OTHER__`), `dimensions = {key: value}` | `revenue_by_category{category=Electronics}` |
| Time series | One `value_series` metric (≤ 1,000 points, grain recorded) **and** headline scalar metrics (latest complete period) | `revenue_monthly` series; `revenue_growth` scalar |
| Distribution/histogram | `value_series` with bin edges and counts | `order_value_deciles` |
| Ratio output | `unit = 'ratio'` (fraction in `[0, 1]`) | `repeat_purchase_rate`, `revenue_share{segment=HIGH_VALUE}` |

Unavailable inputs produce **no metric** and a `module_availability` / metric-level `UNAVAILABLE` record with a reason — never `0` or a placeholder.

## 11.3 Retail metric catalog (SQL source of each)

| Metric (`metric_name`) | Module | Template → column | Unit |
|---|---|---|---|
| `total_revenue` | SALES | `sales_total_revenue.total_revenue` | currency |
| `total_orders` | SALES | `sales_total_orders.total_orders` | count |
| `total_quantity` | SALES | `sales_total_quantity.total_quantity` | quantity |
| `average_order_value` | SALES | `sales_average_order_value.average_order_value` | currency |
| `avg_revenue_per_customer` | SALES | `sales_avg_revenue_per_customer.…` | currency |
| `revenue_growth` | SALES | `sales_growth_latest_period.revenue_growth` | ratio |
| `order_growth` | SALES | `sales_growth_latest_period.order_growth` | ratio |
| `total_customers` | CUSTOMERS | `cust_total_customers.total_customers` | count |
| `new_customers`, `returning_customers` | CUSTOMERS | `cust_new_vs_returning_monthly` (latest complete month, excluding first month) | count |
| `repeat_purchase_rate` | CUSTOMERS | `cust_repeat_purchase_rate.repeat_purchase_rate` | ratio |
| `avg_customer_revenue` | CUSTOMERS | `cust_avg_customer_revenue.…` | currency |
| `avg_orders_per_customer` | CUSTOMERS | `cust_avg_orders_per_customer.…` | count (decimal) |
| `segment_customers`, `segment_customer_share`, `segment_revenue`, `segment_revenue_share`, `segment_aov` | SEGMENTATION | `cust_segment_summary` (dimension `segment`) | count / ratio / currency |
| `rfm_*` distribution series | RFM | `cust_rfm_distribution` | count |
| `revenue_by_product` (top-N), `quantity_by_product`, `product_revenue_share` | PRODUCTS | `prod_*` | currency / quantity / ratio |
| `revenue_by_category`, `quantity_by_category`, `category_revenue_share` | PRODUCTS | `cat_revenue_quantity_contribution` | currency / quantity / ratio |
| `revenue_by_payment_method`, `orders_by_payment_method`, `aov_by_payment_method` | PAYMENT | `pay_summary` | currency / count |
| `revenue_by_country/state/city`, `orders_by_region`, `customers_by_region` | GEOGRAPHY | `geo_*` | currency / count |
| `discount_band_*`, `discount_revenue_correlation` | DISCOUNT | `disc_*` (association flag) | currency / count / score |
| `revenue_monthly`, `revenue_weekly`, `revenue_daily`, `revenue_yearly`, `mom_growth`, `yoy_growth` | TIME | `time_*` | currency / ratio |
| `avg_days_between_orders`, `cohort_retention` | LOYALTY | `loy_*` | days / count |

> `ANALYTICS_SPEC.md` is authoritative for **definitions and thresholds** (e.g., what counts as the "headline" period, minimum observations); this catalog is authoritative for **which SQL produces each metric**. The Power BI DAX measures in `POWERBI_SPEC.md` must be parity-tested against these metrics (§15.5).

---

# 12. Execution, Results, and Lifecycle

## 12.1 Interactive execution contract (maps to API_SPEC §7.12)

| Step | Behavior |
|---|---|
| Submit | API authorizes ownership of `dataset_version_id` via project; validates request; inserts `sql_queries` (`QUEUED`); enqueues |
| Validate | Worker validates (even though the API pre-validates for UX) — **the worker is authoritative** |
| Reject | `status = REJECTED`, `error_code = SQL_REJECTED`, `details` = issue list; **still persisted and audited** (`sql.rejected`) |
| Execute | `RUNNING` → `SUCCEEDED | FAILED | TIMED_OUT`; `duration_ms`, `row_count` recorded |
| Result storage | ≤ cap rows stored as Parquet at `derived/{owner}/{dataset}/v{n}/sql/{query_id}.parquet`; first rows (≤ 256 KB JSON) in `result_preview`; `result_expires_at` = +24 h |
| Read | `GET /sql-queries/{id}/result` paginates from the stored file; expired → `410 SQL_RESULT_EXPIRED` |
| Cancel | `POST /sql-queries/{id}/cancel` → `con.interrupt()`; status `FAILED` with `error_code = CANCELLED` or `CANCELLED` per final enum decision |

> `DATABASE.md` §6.7 defines `sql_queries.status ∈ {PENDING, RUNNING, SUCCEEDED, FAILED, REJECTED, TIMED_OUT}`. User cancellation is recorded as `FAILED` with `error_code = 'QUERY_CANCELLED'` unless a `CANCELLED` value is added by migration (tracked in §17).

## 12.2 Type mapping (engine → API JSON)

| DuckDB type | JSON in API results | Notes |
|---|---|---|
| `DECIMAL(p,s)` | decimal **string** (exact) | e.g. `"82000.0000000000"`; clients format |
| `BIGINT/HUGEINT` | number if ≤ 2^53−1, else string | |
| `INTEGER/SMALLINT` | number | |
| `DOUBLE/FLOAT` | number (`null` for NaN/∞) | `NaN`/`Infinity` never emitted |
| `BOOLEAN` | boolean | |
| `VARCHAR` | string | Server never renders as HTML |
| `DATE` | `"YYYY-MM-DD"` | |
| `TIMESTAMP` | ISO-8601 UTC `…Z` | |
| `LIST/STRUCT/MAP` | JSON (depth-limited) or stringified | Allowed in interactive results; templates return scalars |
| `NULL` | `null` | Rendered `—` by UI |

## 12.3 Error mapping

| Condition | API error | `sql_queries.status` |
|---|---|---|
| Validator rejection | `422 SQL_REJECTED` (+ issue list) | `REJECTED` |
| Binder/runtime SQL error (unknown column, type mismatch, division error) | `422 SQL_EXECUTION_ERROR` (sanitized, no internal paths) | `FAILED` |
| Timeout | `422 SQL_TIMEOUT` | `TIMED_OUT` |
| Memory/resource limit | `422 SQL_EXECUTION_ERROR` (`issue: resource_limit`) | `FAILED` |
| Worker crash | Run/stage retry semantics (templates) or `FAILED` with retry hint (interactive) | `FAILED` |
| Result expired | `410 SQL_RESULT_EXPIRED` | unchanged |

Engine error messages are **sanitized**: file paths, internal catalog names, memory addresses, and stack frames are stripped; positions and column names from the user's own SQL may be retained.

## 12.4 Auditing and retention

- Every attempt (success, failure, rejection) writes `sql_queries` and an `audit_events` row: `sql.executed` / `sql.rejected` with `dataset_version_id`, `duration_ms`, `row_count`, `status` — **never** result values or SQL parameter values (`DATABASE.md` §6.10).
- Query history retention follows the project lifetime; stored result files expire after 24 h; `result_preview` is retained with the row (bounded size).
- Rejected attempts rate-limit the user more aggressively (e.g., > 20 rejections in 10 minutes triggers temporary throttling and a security log event).

## 12.5 Reproducing a result

The Evidence Drawer's **Open in SQL** action prefills the stored `sql_text` and `dataset_version_id`. Re-running against the same version must return **identical** values (golden/reproducibility tests, §15.3). If the user selects a newer version, the UI shows a version-change banner (`DESIGN.md` §6.7).

---

# 13. Performance

| Concern | Strategy |
|---|---|
| Columnar scans | Parquet column pruning/predicate pushdown via views; templates select only needed columns |
| Repeated base aggregations | `customers`, `products`, `orders` are built once per connection; in template mode they are **materialized as temporary in-memory tables** (bounded by `memory_limit`) if the pipeline runs > 3 queries over them; interactive mode uses views |
| Parallelism | Template queries run on a bounded pool (default 4 concurrent connections per run), each with `threads = 2`; the whole stage respects the worker's memory ceiling |
| Window functions | Always partitioned/ordered on stable keys; heavy windows (`NTILE` over customers) run once in `customer_rfm` and are reused |
| Large cardinality | Top-N + `__OTHER__` for dimensional metrics; paginated reads for customer/product tables |
| Result size | Hard cap 10,000 stored rows; UI paginates 200/page |
| Cold start | Parquet fetch dominates; local copy cached per worker for a short TTL (hash-keyed) so a run's many queries reuse it |
| Targets (validated during implementation) | Template query p95 < 2 s on 1M-row datasets with default resources; interactive median < 1 s for typical aggregates |

---

# 14. AI-Assisted SQL (P2 — governed here so it cannot bypass safety)

When AI-assisted SQL (PRD §53, §54) is enabled:

1. The LLM receives **schema only** (relation names, column names/types/roles, grain notes) — **no row values** and no PII.
2. Output is treated as **untrusted text**: it enters the **identical** validator and sandbox as user SQL (`origin = 'AI'`).
3. Answers shown to the user are produced from the **executed result**, never from the model's claims (PRD §97). The number-verification guard applies to any narration (`ARCHITECTURE.md` §11.4).
4. AI-generated SQL is displayed with an `AI-assisted` tag, is editable, and requires the user to click **Run** (no silent execution) except in the future "Ask Your Data" flow, where the same validation applies and the SQL is always shown in the evidence panel.
5. Prompt-injection hardening: column names and sampled labels (if ever included) are passed as quoted data in a delimited section; instructions inside data are ignored; the response schema is enforced.

---

# 15. Testing Requirements (PRD §80–81)

## 15.1 Golden analytics tests (correctness)

Deterministic fixtures in `analytics_engine/tests/golden/` with **hand-verified expected outputs**. Example from PRD §81:

| customer_id | revenue |
|---|---|
| A | 100 |
| A | 200 |
| B | 300 |

Expected: `total_revenue = 600`; `revenue(A) = 300`; `revenue(B) = 300`; `customers = 2`. A test **fails** if any calculation deviates. Each template has at least one golden fixture with exact expected output (including empty-set and `NULL` behavior), covering: partial months, gap months, single-customer data, ties in rankings, derived revenue, missing roles, and negative revenue (returns).

## 15.2 SQL safety corpus (adversarial)

A versioned corpus of statements that **must be rejected** (each with the expected issue code), executed against both the validator **and** the bare sandbox (to prove the engine-level lockdown holds even if the validator were bypassed):

| Input (abridged) | Expected |
|---|---|
| `DROP TABLE transactions` | `not_select` |
| `DELETE FROM transactions` / `UPDATE transactions SET revenue=0` / `INSERT INTO …` / `TRUNCATE …` / `ALTER TABLE …` | `not_select` |
| `SELECT 1; DROP TABLE transactions` | `multiple_statements` |
| `SELECT 1 /* ; */ ; SELECT 2` / `SELECT 1;--` + second statement | `multiple_statements` |
| `WITH x AS (DELETE FROM transactions RETURNING *) SELECT * FROM x` | `forbidden_keyword` |
| `SELECT * INTO new_t FROM transactions` | `forbidden_keyword` |
| `SELECT * FROM read_csv('/etc/passwd')` | `forbidden_function` |
| `SELECT * FROM read_parquet('s3://…')` / `glob('/*')` | `forbidden_function` |
| `SELECT * FROM '/data/other.parquet'` | `literal_table_source` |
| `COPY transactions TO '/tmp/x.csv'` / `EXPORT DATABASE …` | `forbidden_statement` |
| `ATTACH 'x.db'` / `INSTALL httpfs` / `LOAD httpfs` | `forbidden_statement` |
| `PRAGMA database_list` / `SET memory_limit='100GB'` / `RESET …` | `forbidden_statement` |
| `SELECT * FROM information_schema.tables` / `duckdb_tables()` / `pg_catalog.pg_user` | `unknown_relation` / `forbidden_function` |
| `SELECT * FROM main.transactions` | `qualified_name_not_allowed` |
| `SELECT current_setting('x')` / `getenv('HOME')` | `forbidden_function` |
| `SELECT random()`, `SELECT now()` | `nondeterministic_function` |
| `SELECT * FROM generate_series(1, 1e12)` / `range(…)` | `forbidden_function` |
| Unicode/homoglyph keyword tricks, case/spacing variants, quoted identifiers (`"DROP"`), comment-embedded statements | Rejected or harmless per AST (must never execute a non-SELECT) |
| Cross-tenant probes (`SELECT * FROM users`) | `unknown_relation` |
| 25-level nested subqueries / 20 joins / 5,000 `OR` terms | `too_complex` |
| 25,000-char statement | `too_long` |
| Valid `SELECT customer_id, SUM(revenue) FROM transactions GROUP BY 1` | **Accepted** |

**Engine-level lockdown tests** run the same hostile statements through a connection created with the production lockdown **without** the validator and assert the engine itself refuses (S1–S5). Any statement that succeeds is a **release blocker**.

## 15.3 Property-based and invariant tests (hypothesis)

| Invariant | Statement |
|---|---|
| Revenue partitions | `SUM(revenue_by_category) + revenue_unclassified = total_revenue` |
| Segments partition customers | `SUM(segment_customers) = total_customers`; shares sum to 1 (± 1e-9) |
| Segments partition revenue | `SUM(segment_revenue) = SUM(customers.total_revenue)` |
| RFM bounds | `1 ≤ r,f,m ≤ 5`; `rfm_score` is a 3-character string of digits 1–5; one row per customer |
| Orders reconcile | `SUM(order_revenue) = total_revenue` (for rows with non-null `transaction_id`) |
| AOV identity | `AOV × total_orders = SUM(order_revenue)` within decimal tolerance 1e-9 |
| Growth sanity | `revenue_growth = (cur − prev)/prev` recomputed in Python from persisted monthly metrics equals SQL result |
| Idempotence | Re-running a template on the same version yields byte-identical results |
| Row-order independence | Shuffling input row order does not change any template result (determinism of tie-breaks) |
| Pareto monotonicity | `cumulative_revenue_share` is non-decreasing and ends at 1.0 |
| No negative counts | All count columns ≥ 0 |

## 15.4 Sandbox conformance tests

Run on every DuckDB version bump and in CI:

1. Base views remain queryable after lockdown; a non-registered file path is unreadable.
2. Configuration is locked (`SET`/`PRAGMA` fail at engine level).
3. No extension install/load; no network call is attempted (egress-denied container test).
4. Memory/timeout/row-cap enforcement; interrupt cancels long queries within a bounded time.
5. Per-query temp directory is removed after success, failure, timeout, and cancel.
6. The worker process cannot connect to PostgreSQL or any other internal service (network policy test).

## 15.5 Template lint, parity, and regression

- **Template lint (CI):** parse every template; assert relations/functions allow-listed, parameters declared and typed, deterministic `ORDER BY`, aliases present, `output` matches executed projection on the golden dataset, `requires.roles` consistent with referenced columns.
- **Availability tests:** for each template, datasets missing a required role yield `UNAVAILABLE` with the documented reason and the template is **not executed**.
- **Metric parity:** each SQL-derived metric is compared with an **independent Python/Polars reference calculation** on golden data; DAX measure definitions (POWERBI_SPEC) are parity-checked against these metric values.
- **Snapshot regression:** results of the template library on a frozen sample dataset are snapshotted; any diff requires a `template_version` bump and `PIPELINE_VERSION` bump.
- **Report-consistency test:** every number in generated reports/decks resolves to a persisted metric produced by these templates (PRD §60).

---

# 16. Versioning and Change Control

| Item | Rule |
|---|---|
| `sql_spec_version` | Semantic version of this document's relations + safety rules (current: `1.0`) |
| `template.version` | Integer per template; **any** SQL/column change increments it |
| `PIPELINE_VERSION` | Bumped on **any** change to relation definitions, template SQL, metric bindings, segmentation rules, or sandbox behavior that can alter results |
| Run reproducibility | `analysis_runs.pipeline_version` + `config` + dataset version determine the exact template versions used; old runs remain readable and reproducible by pinning the engine version |
| Deprecation | Retired template keys are never reused; they stay readable for historical runs |
| Review | Changes to templates or validator require: golden-test update, safety-corpus run, and `DECISIONS.md` entry if behavior changes |

---

# 17. Open Items and Decisions to Record (`DECISIONS.md`)

| ID | Item | Impact |
|---|---|---|
| ADR-005 (accepted) | DuckDB sandbox over Parquet | This document |
| ADR-017 (proposed) | Dedicated `sql` worker queue vs routing key on `analysis` | If a separate queue is chosen: migrate `ck_jobs__queue` (`DATABASE.md` §6.5) and update `ARCHITECTURE.md` §9.2 |
| ADR-018 (proposed) | Add `CANCELLED` to `sql_queries.status` | Migration of `ck_sql_queries__status`; update `API_SPEC.md` enum |
| ADR-019 (proposed) | Add `result_sha256` to `sql_queries` for result-integrity/reproducibility checks | Additive migration; optional |
| ADR-016 (open) | Decimal vs double for stored metric values | Interacts with §6 (ratios as `DOUBLE`, stored with 10 dp) |
| — | Spearman in SQL vs Python | Current decision: Python (tie handling) — revisit if DuckDB gains average-rank support |
| — | Cost/margin role | Adds a `COST` semantic role and margin templates; requires PRD update (§23) |
| — | Confirm pinned DuckDB version supports `allowed_paths` + `lock_configuration` as assumed (§4.1) | Otherwise use the materialization fallback |
| — | Cohort retention ratios (engine-side) and headline-period rules | Defined in `ANALYTICS_SPEC.md` |

---

# 18. Traceability to PRD

| PRD Section | SQL_SPEC Section |
|---|---|
| §5.2–5.4, §95–97 Evidence, AI explains/analytics calculates, reproducibility | §1.1, §3, §11, §12.5, §14, §15 |
| §37 Sales analysis | §10.1 |
| §38 Customer analysis | §10.2 |
| §39 Segmentation | §5.7, §10.2 |
| §40 RFM | §5.7, §10.2 |
| §41 Product analysis | §5.4, §10.3, §10.4 |
| §42 Discount analysis | §5.8, §10.7 |
| §43 Payment analysis | §10.8 |
| §44 Geographic analysis | §10.6 |
| §45 Time-based analysis | §5.5, §10.1, §10.5 |
| §46 SQL analytics engine | §3, §5, §9, §10 |
| §47 SQL query explorer (Question, SQL, status, result, time) | §9.1, §12.1, `API_SPEC.md` §7.12 |
| §48 SQL safety | §4, §7, §8, §15.2, §15.4 |
| §49 Business metrics (machine-readable) | §11 |
| §50–51 Insights from verified metrics; never fabricate | §11 (insights consume metrics only) |
| §57 Power BI dashboard pages (purchase behavior etc.) | §10.9, §15.5 (DAX parity) |
| §60 Evidence-based reports, single source of truth | §11, §15.5 |
| §65–66, §116 Partial analysis / unavailable features | §9.2, §11.2 |
| §78–79 Observability / auditing | §12.4 |
| §80–81 Testing, analytics correctness | §15 |
| §82 Security (no arbitrary SQL, injection) | §4, §7, §8, §15.2 |
| §112–114 Currency, dates, precision | §5.1, §5.5, §6, §12.2 |
| §126 Prohibited shortcuts (no hardcoded results, no unrestricted SQL) | §1.1, §7, §9.2, §15 |
