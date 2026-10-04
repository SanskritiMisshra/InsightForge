# InsightForge — Analytics Specification (ANALYTICS_SPEC.md)

**Version:** 1.0
**Methodology version:** `1.0` (data-quality scoring) · **Segmentation rules version:** `1` · **Insight template version:** `1`
**Initial `PIPELINE_VERSION`:** `1.0.0`
**Status:** Authoritative for all analytics-engine behavior. Section 24 lists decisions that close gaps found between the other documents; each one names the follow-up edits required elsewhere (PRD §127).
**Depends on:** `PRD.md` (§5, §21–45, §49–52, §60, §65–66, §94–97, §112–114), `ARCHITECTURE.md` (§8, §9.5, §10, §11.4, §14, §20), `DATABASE.md` (§4, §6, §7), `API_SPEC.md` (§2.3, §7.5–7.13)
**Consumed by:** `SQL_SPEC.md`, `POWERBI_SPEC.md`, `REPORTING_SPEC.md`, `AI_SPEC.md`, `TESTING.md`

> **This document is the single definition of every number InsightForge produces.** If a figure shown anywhere in the product (dashboard, chart, insight, report, deck, Power BI measure) cannot be traced to a definition in this document, that is a defect.

---

# 1. Purpose, Scope, and Authority

## 1.1 What this document defines

1. How raw files become typed, lossless, columnar datasets (ingest, type inference).
2. How columns are profiled and assigned business meaning (semantic roles).
3. How data quality is scored, explained, and acted on (including the exact formulas PRD §24 requires).
4. How cleaning operations behave, in what order, and what they log.
5. The analytical relations (tables) available to SQL, Power BI, and reports.
6. EDA, statistics, correlation, outlier methods, and chart-spec selection.
7. Every Retail-domain metric: definition, grain, prerequisites, edge cases.
8. Customer segmentation, RFM, and loyalty rules.
9. The metric record, registry, and provenance contract.
10. The insight and recommendation engine: rule catalog, confidence, ranking, language rules.
11. Module availability, pipeline stage behavior, progress weighting, partial analysis.
12. Determinism, reproducibility, versioning, resource limits, and test fixtures.

## 1.2 What it does not define

| Out of scope | Where it lives |
|---|---|
| Full SQL question library and validator rules | `SQL_SPEC.md` (this document fixes relations, dialect, and the metric ↔ SQL contract, §17) |
| DAX, dashboard layouts, import steps | `POWERBI_SPEC.md` (this document fixes model construction rules, §18) |
| Report/deck layout and templates | `REPORTING_SPEC.md` (this document fixes the data bundle and limitations logic, §19) |
| LLM prompts, number guard internals | `AI_SPEC.md` (this document fixes display formatting that the guard matches against, §15.6) |
| HTTP shapes | `API_SPEC.md` |
| DDL | `DATABASE.md` |

## 1.3 Conventions

- **MUST / MUST NOT / SHOULD / MAY** are used in their RFC 2119 sense. A MUST is covered by at least one automated test (§22).
- **Config keys** appear as `config.path.to.key`. Every default is listed once, in §23.
- **Roles** are the `semantic_role` enum in `DATABASE.md` §4. **Modules** are the analysis modules in §16.
- Python snippets are normative for *behavior*; names and signatures MAY change if behavior and tests do not.
- "Rows" means rows of the dataset version being analyzed after the stage's own filtering, unless stated otherwise.

## 1.4 Technology baseline

| Concern | Choice | Rule |
|---|---|---|
| Dataframes | Polars (primary), PyArrow for Parquet I/O | pandas only at library boundaries (e.g., a reader that returns pandas) and never for metric computation |
| SQL | DuckDB, in-process, in-memory, read-only | All **monetary aggregation** runs here over `DECIMAL` columns (§4.2) |
| Statistics | NumPy / SciPy | Float64 only; never used for monetary sums |
| String similarity | Python stdlib `difflib` | No new runtime dependency for fuzzy matching (PRD §126) |
| SQL parsing | `sqlglot` | Validator only; not used to build metrics |

New runtime dependencies for the engine require a one-line justification in the PR (ARCHITECTURE §5). One such dependency is already implied by this document and needs a decision: **XLSX reader** (`fastexcel`/calamine vs `openpyxl` read-only) — recorded as proposed **ADR-017** in §24.

---

# 2. Engine Principles and Invariants

## 2.1 Principles (operational form of PRD §5)

| # | Principle | Operational rule |
|---|---|---|
| P1 | Deterministic | Same dataset-version bytes + `config` + `PIPELINE_VERSION` ⇒ identical persisted outputs (§3.5). No wall-clock reads, no unseeded randomness, no network in analytic code paths. |
| P2 | Evidence-first | Every number the engine persists is a `metrics` record with `calculation`, provenance, and (where it comes from SQL) a `sql_query_id`. Text that contains numbers is rendered from metric IDs (§15). |
| P3 | Lossless raw | Dataset version 1 never loses information the user uploaded (§5.7). All lossy steps are cleaning operations that create a new version and a log entry. |
| P4 | Unavailable ≠ failed | Missing prerequisites produce an explained `Unavailable` result (§16), never an exception and never a fabricated value. |
| P5 | Conservative by default | Defaults flag rather than remove or impute. Destructive options require explicit parameters and are logged with reasons (§9). |
| P6 | Association ≠ causation | Any metric or insight derived from a correlation, comparison between groups, or discount/payment/segment contrast carries `is_association = true` (§15.4). |
| P7 | One source of numbers | Reports, decks, charts, Power BI, and AI text consume persisted metrics by ID only (PRD §60). |
| P8 | Preserve precision | Money is exact decimal; statistics are float64; rounding happens only at persistence (§4.3) and display (§15.6). |

## 2.2 Machine-checkable invariants

These hold for every completed run and are asserted by the property-test suite (§22.3). A violation is a release blocker.

| ID | Invariant |
|---|---|
| INV-01 | Cleaning never increases the row count; `rows_after = rows_before − rows_removed` for every logged operation. |
| INV-02 | `Σ category_revenue (persisted top-N) + category_revenue[__other__] = total_revenue` (exact decimal equality). Same for products, payment methods, and each geography level. |
| INV-03 | `Σ segment_customers = total_customers` over all four segments (when SEGMENTATION is available). |
| INV-04 | Every RFM component score `∈ [1, bins]`; RFM score string length `= 3`. |
| INV-05 | `repeat_customers + one_time_customers = total_customers` (customers with ≥ 1 order). |
| INV-06 | `0 ≤ every ratio-unit share ≤ 1`; growth rates are exempt. |
| INV-07 | Re-running the same `run_key` (also across worker restarts and thread counts 1 and N) yields byte-identical `value` strings for every metric. |
| INV-08 | No metric is persisted with `value = NaN` or `±Infinity`; undefined results are **absent** with a recorded reason (§14.5). |
| INV-09 | Every insight has ≥ 1 evidence metric; every recommendation has ≥ 1 source insight (also enforced in DB). |
| INV-10 | Every `display_value` in an insight/recommendation equals `format_display(metric)` for its bound metric (§15.6). |
| INV-11 | A dataset version's content hash recorded at creation equals the hash of the bytes loaded by any later stage. |
| INV-12 | If `PURCHASE_DATE` is unmapped, no metric with a time `dimension` exists in the run. |

---

# 3. Execution Model

## 3.1 Package layout (normative responsibilities)

```text
insightforge_engine/
├── ingest/          # readers, structural validation, null/type inference, Parquet v1 writer       (§5)
├── profiling/       # dataset and column profiles                                                  (§6)
├── semantics/       # semantic role detection + validation                                         (§7)
├── quality/         # scoring, missingness, duplicates, outliers                                   (§8)
├── cleaning/        # operation registry, preview/apply, log                                       (§9)
├── transform/       # analytical relations (transactions, orders, customers_dim, …)                (§10)
├── eda/ + stats/    # numeric/categorical/time/correlation + chart specs                          (§11)
├── domains/retail/  # metric definitions, segmentation, RFM, loyalty, insight rules                (§12–15)
├── metrics/         # registry, MetricRecord, dimension canonicalization                           (§14)
├── sqlgen/          # SQL templates bound to metrics                                               (§17)
├── powerbi/         # star schema + measure builders                                               (§18)
├── pipeline/        # Stage protocol, DAG, RunContext, progress                                    (§3.2–3.4)
├── common/          # canonical JSON, hashing, decimal helpers, seeds, formatting                  (§4)
└── version.py       # PIPELINE_VERSION
```

The engine MUST NOT import `fastapi`, `celery`, `sqlalchemy`, or any HTTP/DB client (ARCHITECTURE §6). I/O goes through two injected interfaces:

```python
class DataReader(Protocol):
    def open_version(self, version: VersionHandle) -> pl.LazyFrame: ...      # verifies content_sha256 (INV-11)
    def open_derived(self, run_id: str, name: str) -> pl.LazyFrame: ...

class ArtifactWriter(Protocol):
    def write_version(self, frame: pl.LazyFrame, meta: VersionMeta) -> WrittenVersion: ...   # Parquet + sha256
    def write_derived(self, run_id: str, name: str, frame: pl.LazyFrame) -> WrittenArtifact: ...
```

## 3.2 RunContext

```python
@dataclass(frozen=True)
class RunContext:
    run_id: str
    run_key: str                       # sha256 (see §3.5)
    version: VersionHandle             # exactly one dataset version
    mapping: SemanticMapping           # validated roles for this version
    config: AnalysisConfig             # fully resolved: defaults applied, `as_of_date` frozen (§4.5)
    domain: Domain                     # retail plugin
    reader: DataReader
    writer: ArtifactWriter
    pipeline_version: str              # PIPELINE_VERSION
    seed: int                          # derive_seed(run_key, "run")
    cancel: CancelToken                # polled at checkpoints (§3.4)
```

`AnalysisConfig` is resolved **once at run creation** by the API/service layer (defaults merged, `as_of_date` set) and stored in `analysis_runs.config`. The engine never reads defaults from the environment or clock.

## 3.3 Stage contract and stage table

The pipeline is a linear chain of idempotent stages (ARCHITECTURE §8.3). Each stage implements `plan(ctx) -> StageApplicability` (pure, cheap) and `run(ctx) -> StageResult` (idempotent).

| # | Stage (`PRD §61`) | Reads | Writes | Progress weight |
|---|---|---|---|---:|
| 1 | `VALIDATING` | version v1 (or run's version) | verification of hash, schema sanity, module plan | 5 |
| 2 | `PROFILING` | version | `dataset_profiles`, `dataset_columns` stats, PII flags, **semantic mapping proposal** (§7) | 10 |
| 3 | `CLEANING` | version | `quality_report`, `quality_issues` (+ cleaning recommendations; **does not mutate** the version, §3.6) | 10 |
| 4 | `TRANSFORMING` | version | run-scoped derived tables: `transactions`, `orders`, `customers_dim`, `products_dim`, `date_dim` (§10) | 10 |
| 5 | `EDA` | derived tables | `eda_results` (+ metrics for quality/EDA statistics) | 20 |
| 6 | `SQL_ANALYSIS` | derived tables via DuckDB | `sql_queries`, business `metrics` (§12–14, §17) | 25 |
| 7 | `INSIGHT_GENERATION` | metrics | `insights`, `insight_metrics`, `recommendations`, `recommendation_sources` | 10 |
| 8 | `POWERBI_PREPARATION` | derived tables + metrics | `powerbi_models` package (only if requested) | 5 |
| 9 | `REPORT_GENERATION` | persisted records | report artifacts (only if requested at run creation, §3.6) | 5 |
| 10 | `PRESENTATION_GENERATION` | persisted records | deck artifacts (only if requested at run creation) | 0 (weights renormalized) |

Stages that are not requested are recorded as `SKIPPED`; their weights are removed and the remainder renormalized so `progress_pct` always reaches 100 at completion. Within a stage, `stage.progress` is reported as the fraction of that stage's sub-tasks completed.

> **Naming note.** The stage name `CLEANING` is the PRD's. In a **run**, this stage *assesses* quality and *recommends* cleaning; applying cleaning is a separate, user-triggered, versioned operation (`POST /dataset-versions/{id}/cleaning`, API §7.6) that creates a new dataset version, after which a new run is created for that version. See §24 (R-05).

## 3.4 Sub-tasks, cancellation, and failure scope

Each stage is made of named **sub-tasks** (e.g., `EDA` → `numeric`, `categorical`, `time`, `correlation`, `outliers`; `SQL_ANALYSIS` → one sub-task per module). Rules:

1. A sub-task failure marks **that module/sub-task** `FAILED` with a user-safe reason and does not stop siblings.
2. A stage is `COMPLETED` if at least one sub-task completed, `UNAVAILABLE` if every sub-task was unavailable, and `FAILED` only if the stage could not run at all (e.g., unreadable version, hash mismatch) or every sub-task failed.
3. The run is `FAILED` only for a failed **blocking** stage (`VALIDATING`, `PROFILING`, `TRANSFORMING`). Failures in later stages leave the run `COMPLETED` with `warnings` and module-level `FAILED` states (API §7.7). Module-level retry is specified in §16.5.
4. Cancellation is cooperative: `ctx.cancel.check()` is called between sub-tasks and every ≈ 5 s inside long loops; on cancel the stage exits without partial writes (outputs are committed per sub-task, atomically).

## 3.5 Determinism contract

| Rule | Requirement |
|---|---|
| Ordering | Every group-by output that is persisted or numbered (ranks, top-N, quantile ties) MUST have an explicit total order: primary sort key(s) followed by the natural key ascending. Unordered output is a defect. |
| Row identity | `line_id` = zero-based ordinal of the row within the dataset version Parquet (stable because versions are immutable). Tie-breaks and "first occurrence" use `line_id`. |
| Floating point | Float64 reductions that feed persisted numbers MUST use an order-independent method: either exact accumulation (Decimal / integer) or `math.fsum` over values sorted ascending. Parallel Polars float sums are not guaranteed bitwise-stable across thread counts; test INV-07 runs with 1 and N threads. |
| Randomness | Only seeded sampling is allowed: `derive_seed(run_key, purpose)` (below). Sampling MUST pick by `line_id` hash order, not by RNG draw order over unordered data. |
| Collation | String comparison for ordering uses Unicode NFC-normalized, case-sensitive byte order (UTF-8) unless a metric states otherwise. |
| Time | The only "now" the engine knows is `config.as_of_date` (§4.5). `computed_at` on metrics is supplied by the worker and is **excluded** from reproducibility comparisons. |
| Library pinning | Polars, DuckDB, PyArrow, NumPy, SciPy versions are pinned in the lockfile. Upgrading any of them requires running the golden suite; if any persisted value changes, `PIPELINE_VERSION` is bumped (§3.7). |

```python
def derive_seed(run_key: str, purpose: str) -> int:
    h = hashlib.sha256(f"{run_key}\x1f{purpose}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")
```

## 3.6 Report/deck generation and run completion

PRD §61 lists report and presentation generation as pipeline states, while API §7.15 requires a `COMPLETED` run before generating artifacts on demand. Both are supported:

- **Requested at run creation** (`generate.report_formats` / `generate.presentation` / `generate.powerbi`): the corresponding stages execute inside the run; the run becomes `COMPLETED` only after they finish.
- **Requested later** (the normal UI path): stage rows for those stages stay `SKIPPED` in the original run (the run's history is never mutated). The artifact has its own lifecycle (`reports.status`, `presentations.status`, `powerbi_models.status`) and is tracked as a `generate`-queue job.

Either way, generators read only persisted records through a `ReportBundle` (§19).

## 3.7 Versioning rules

| Version | Bump when | Effect |
|---|---|---|
| `PIPELINE_VERSION` (`MAJOR.MINOR.PATCH`) | **MAJOR:** any change that alters a persisted number or text for the *same input* (definition, threshold, algorithm, rounding, library upgrade that changes output). **MINOR:** additive (new metric, module, insight rule, chart type) with no change to existing outputs. **PATCH:** no output change (performance, logging, refactor). | Part of `run_key` ⇒ a new run key, never a mutation of past results |
| `methodology_version` | The data-quality scoring formula, weights, or sensitivities change | Stored on `data_quality_reports` |
| `segmentation_rules_version` | Any segmentation or RFM rule/threshold changes | Stored in `analysis_runs.config` and shown in the UI rules disclosure |
| `template_version` | Insight/recommendation text templates change | Stored on each insight/recommendation |

Golden-snapshot diffs in CI MUST be reviewed whenever any version above changes (ARCHITECTURE §23).

---

# 4. Numeric Policy and Canonical Contracts

## 4.1 Types by purpose

| Purpose | Type | Notes |
|---|---|---|
| Monetary amounts (`REVENUE`, `PRICE`, discount amounts) | **Exact decimal**, `DECIMAL(38,10)` | Closes proposed ADR-016 (§24, R-09) |
| Counts | `int64` | |
| Statistics (mean, std, quantiles, correlation, z-scores) | `float64` | Never used for sums that become reported money |
| Ratios / shares / growth | Computed from exact numerators/denominators, divided once, rounded per §4.3 | |
| Dates / timestamps | UTC timestamps (`datetime[us, UTC]`) and calendar dates in the reporting time zone (§4.5) | |

## 4.2 Where each computation runs

| Computation | Engine | Reason |
|---|---|---|
| Money sums, group-bys, order/customer aggregations, shares | **DuckDB** over `DECIMAL(38,10)` | Exact; results are reproducible by the stored SQL (evidence) |
| Profiling, quality, outliers, correlation, histograms, RFM scoring, segmentation | **Polars + NumPy/SciPy** | Row-wise logic and statistics |
| Derived-table construction (§10) | Polars (lazy) → Parquet | |

A metric computed in Python has `calculation_kind = PYTHON` and a human-readable `calculation` string (e.g., `RFM monetary score = midrank_quantile(customer_total_revenue, bins=5)`); one computed in SQL has `calculation_kind = SQL` and a `sql_query_id`. The kind is encoded as a prefix of the `calculation` text (`SQL: …` or `PYTHON: …`), so no schema change is needed.

## 4.3 Rounding and persistence

- Persisted `value` is rounded **once**, to 10 decimal places, with **round-half-even** (`ROUND_HALF_EVEN`), and written as `numeric(38,10)`. API exposes it as the exact decimal string (API §2.3).
- Divisions use `Decimal` with context precision 50; the quotient is then quantized as above.
- Float64 statistics are converted via `Decimal(repr(x))` (shortest round-trip representation) before quantization, so `float → numeric` is deterministic.
- `value_f64` (API) is derived from the stored decimal at read time.
- Display rounding (§15.6) never feeds back into any computation.

## 4.4 Hashing and canonical JSON

```python
def canonical_json(obj: Any) -> bytes:
    """Sorted keys, no whitespace, NFC strings, shortest-round-trip floats, no NaN/Inf."""
    def norm(o):
        if isinstance(o, str):   return unicodedata.normalize("NFC", o)
        if isinstance(o, float):
            if not math.isfinite(o): raise ValueError("non-finite float in canonical JSON")
            return 0.0 if o == 0.0 else o           # -0.0 -> 0.0
        if isinstance(o, dict):  return {norm(k): norm(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [norm(v) for v in o]
        return o
    return json.dumps(norm(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def sha256_tag(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()
```

| Hash | Definition |
|---|---|
| `config_hash` | `sha256_tag(canonical_json(config_without_mapping_and_volatile))`. Volatile keys excluded: none (all config is frozen, including `as_of_date`). |
| `mapping_hash` | `sha256_tag(canonical_json(sorted([{"column": name, "role": role} …])))` over columns with `role ≠ UNKNOWN`, plus `discount_kind` and `revenue_basis` (§7.6). Column **names** (normalized) not ordinals, so reordering columns does not change the hash. |
| `run_key` | `sha256_tag(b"\x1f".join([version_id, config_hash, pipeline_version, domain_key, mapping_hash]))` (unit-separator joined to prevent ambiguity). |
| `dimension_key` | `"" ` for no dimensions; else `sha256(canonical_json(dimensions)).hexdigest()[:32]` (DATABASE §7). |
| Operation-set `config_hash` | `sha256_tag(canonical_json(ordered canonicalized operation list))` after canonical ordering (§9.2). |

## 4.5 Time handling

| Setting | Default | Meaning |
|---|---|---|
| `config.time.source_time_zone` | `UTC` | Zone assumed for **naive** (timezone-less) timestamps at parse time |
| `config.time.time_zone` | `UTC` | Reporting zone: `purchase_date` = calendar date of the UTC instant converted to this zone; all period boundaries use it |
| `config.time.week_start` | `MONDAY` | Weeks are ISO weeks; labeled `YYYY-Www` |
| `config.as_of_date` | date of `datasets.upload_completed_at` in the reporting zone, **frozen at run creation** | The only "today" the engine uses (future-date validity, recency fallbacks). Never read from the clock inside the engine. |

Dates that are already timezone-aware keep their instant; dates that are date-only (no time) are treated as midnight in `source_time_zone` and keep a `is_date_only` marker in column stats.

---

# 5. Ingestion and Type Inference

## 5.1 Principle

The engine reads every file as **text first** and infers types itself. Letting a reader auto-infer types is forbidden: it is not deterministic across versions and silently corrupts identifiers (leading zeros, long numerics, scientific notation).

## 5.2 Readers

| Format | Behavior |
|---|---|
| **CSV** | Detect encoding in order: BOM → UTF-8 strict → `charset-normalizer` candidates with confidence ≥ 0.8 → fail `DATASET_ENCODING_UNSUPPORTED`. Delimiter sniffed from the first 64 KB over `, ; \t \|`, chosen by highest consistent column count across the first 1,000 records. Quote `"`, escape by doubling. Header row is required; a file whose first row looks like data (all cells parse as numbers/dates) is still treated as a header (the user can re-upload) and a warning `HEADER_LOOKS_LIKE_DATA` is raised. All columns read as `Utf8`. Rows with a different field count than the header: ≤ 0.1 % of rows are **kept, padded/truncated, and counted** in `ingest.malformed_rows`; above 0.1 % ⇒ `DATASET_INVALID_STRUCTURE`. |
| **XLSX** | `.xlsm`/macros/external links rejected (`DATASET_UNSAFE_CONTENT`). The **first non-empty visible sheet** is used; its name and the other sheets' names are recorded in `ingest.sheets` (V1 does not merge sheets). Header row = first non-empty row. Merged cells: value kept in the top-left cell only. Native Excel dates arrive as typed datetimes and keep their type; all other cells are converted to their displayed text value. Formulas read as cached values; a formula cell with no cached value is null and counted. |
| **JSON** | Accepted shapes: (a) top-level array of objects; (b) NDJSON; (c) an object with **exactly one** key whose value is an array of objects. Anything else ⇒ `DATASET_INVALID_STRUCTURE`. Union of keys across records forms the columns (first-seen order). Nested objects are flattened with `__` up to depth 3 (`address.city` → `address__city`); deeper structure and arrays are serialized to a JSON string and typed `TEXT`, with a warning. |

All readers run in a resource-limited process (row/column/size/time caps from `MAX_ROWS`, `MAX_COLUMNS`, `MAX_UPLOAD_BYTES`) and stream into Parquet in row groups of 128 k rows.

## 5.3 Column-name normalization

Applied to produce `dataset_columns.name`; the raw header is kept as `original_name`.

1. Unicode NFKC, trim, collapse internal whitespace.
2. Lowercase.
3. Replace every run of characters outside `[a-z0-9]` with `_`; trim `_`.
4. Split camelCase *before* lowercasing (so `UnitPrice` → `unit_price`, `CustomerID` → `customer_id`).
5. If the result is empty → `col_{ordinal}`; if it starts with a digit → prefix `c_`.
6. Collisions: append `_2`, `_3`, … in ordinal order.
7. Reserved names used by derived relations (`line_id`, `order_id`, `purchase_ts`, `purchase_date`, `revenue_is_derived`, `discount_rate`) get the suffix `_raw` if they appear as *unmapped* user columns (§10.2).

## 5.4 Null tokens

After trimming whitespace, a cell is **null** if it is empty or, case-insensitively, one of:
`null, none, nan, n/a, #n/a, na, nil, -, --, ?, missing, unknown`.

`config.ingest.null_tokens` can override this list per project. Two cautions are enforced in code, not left to the user: (a) `na` is **not** treated as null in a column whose values are otherwise ≥ 90 % two-letter uppercase codes (e.g., country codes where `NA` = Namibia); (b) `unknown` is **kept** as a value in columns that become `CATEGORICAL` (it is a legitimate category label) and only treated as null for numeric/date inference. The per-token counts replaced are recorded in the profile (`stats.null_tokens`).

## 5.5 Type inference algorithm

Input: the non-null text values `V` of a column (`n = |V|`). One full pass computes all parse-success counts; sampling is not used for type decisions.

**Step 0 — Identifier-by-name gate.** If the normalized name matches `(^|_)(id|uuid|guid|sku|code|key|ref|no|number|num)($|_)` **or** equals a known identifier synonym (§7.3 for `CUSTOMER_ID`, `TRANSACTION_ID`, `PRODUCT_ID`) and the values are text or integers ⇒ `IDENTIFIER`. Identifiers are never parsed as numbers (leading zeros are preserved).

**Step 1 — Boolean.** All values ∈ `{true,false,t,f,yes,no,y,n}` (case-insensitive) ⇒ `BOOLEAN`. A column containing only `0/1` is `BOOLEAN` only if the name matches `^(is|has|was|flag)_|_flag$|(active|returned|refunded|cancelled)`; otherwise it stays numeric.

**Step 2 — Numeric parse.** Normalize each value with these rules, in order: strip currency symbols/codes (`₹ $ € £ ¥ INR USD EUR GBP`), strip spaces and `'`, treat `(123.45)` as `-123.45`, trailing `-` as negative, `%` suffix recorded and removed (`pct_suffix=true` in stats), thousands separators detected as: Indian grouping `1,23,456.78`, Western `1,234,567.89`, or European `1.234.567,89` — the style is chosen by the **majority of values that disambiguate** (a value with both separators, or a group length ≠ 3 with a comma). If no value disambiguates, a single comma followed by exactly 3 digits is a thousands separator and a single comma followed by 1–2 digits is a decimal comma. Exponent notation (`1.2e5`) is accepted and forces `FLOAT`.

Let `p_num = parsed / n`.

**Step 3 — Date parse** (if numeric `p_num < 0.98`), per §5.6. Let `p_date = parsed / n`.

**Step 4 — Decision.**

| Condition | Type |
|---|---|
| `p_num ≥ 0.98` and all parsed values integral and within `int64`, no decimal point | `INTEGER` |
| `p_num ≥ 0.98`, max decimal places over parsed values ≤ 4, no exponent | `NUMERIC` (fixed-point, stored `DECIMAL(38,10)`) |
| `p_num ≥ 0.98` otherwise | `FLOAT` |
| `p_date ≥ 0.98` and every parsed value has no time part | `DATE` |
| `p_date ≥ 0.98` otherwise | `DATETIME` |
| text, `unique_pct ≥ 0.95`, `n ≥ 50`, mean length ≤ 40, < 20 % of values contain a space | `IDENTIFIER` |
| text, `unique_count ≤ min(1000, max(50, ⌈0.05·n⌉))` and mean length ≤ 50 | `CATEGORICAL` |
| integer sequence `1..n` strictly increasing (row index) | `IDENTIFIER` |
| everything else | `TEXT` |

Ties between numeric and date are impossible at a 0.98 threshold; if both exceed it (e.g., `20260131` integers), the name gate decides: names matching `date|time|timestamp|_at$|_on$` choose date (`%Y%m%d`), otherwise numeric.

**Mixed columns.** If the best type's parse rate is in `[0.80, 0.98)`, the column is typed `TEXT` for storage, but `detected_type` records the *intended* type and `stats.parse_rate` is stored; the quality engine raises a `TYPE_INCONSISTENCY` issue (§8.5) and the cleaning recommendation `STANDARDIZE_TYPES` is proposed. Below 0.80 ⇒ plain `TEXT`.

Low-cardinality integers (≤ 12 distinct values, e.g., ratings 1–5, age buckets) remain `INTEGER`; EDA treats them as **discrete** (§11.2).

## 5.6 Date and datetime parsing

Candidate formats are tried in this fixed order; the first that parses ≥ 98 % of values wins for the whole column (a single format per column keeps results explainable). Mixed formats within a column ⇒ `FORMAT_INCONSISTENCY` issue and the dominant format's share is recorded.

```text
ISO:        %Y-%m-%d  %Y-%m-%dT%H:%M:%S[.%f][Z|±HH:MM]  %Y-%m-%d %H:%M:%S[.%f]  %Y/%m/%d  %Y%m%d
DAY-FIRST:  %d/%m/%Y  %d-%m-%Y  %d.%m.%Y  %d/%m/%Y %H:%M[:%S]  %d-%b-%Y  %d %b %Y  %d %B %Y
MONTH-FIRST:%m/%d/%Y  %m-%d-%Y  %m/%d/%Y %H:%M[:%S]  %b %d, %Y  %B %d, %Y
EXCEL:      numeric serials in [20000, 80000] only when the column name matches date/time
```

**Day/month ambiguity.** For the slash/dash numeric families, evaluate all values: if any value has a first component > 12 ⇒ DAY-FIRST; if any value has a second component > 12 ⇒ MONTH-FIRST; if both occur ⇒ the column is `FORMAT_INCONSISTENCY`. If **no** value disambiguates, the project setting `config.ingest.date_order` (`DMY` default for INR/GBP/EUR/AUD…, `MDY` for USD, resolved from project currency at creation and stored) decides, and a warning `DATE_ORDER_ASSUMED` is attached to the column and surfaced in the UI (the assumption is part of the config, so it is reproducible and overridable).

Two-digit years pivot at 69 (`00–68` → 2000s, `69–99` → 1900s). Impossible dates (`31/02/2026`) count as parse failures.

## 5.7 Dataset version 1 (lossless ingest)

Version 1 is written to `raw/{owner}/{dataset}/ingested/v1.parquet` with these rules:

1. A column is stored in its **inferred physical type only if 100 % of non-null values parse** (value-preserving: `"₹1,200.50"` → `1200.5000000000` is considered preserving; `"12x"` is not). Otherwise it is stored as `Utf8` and `stats.storage_dtype = "Utf8"`.
2. Null tokens are stored as real nulls (the token text is recorded only as counts).
3. No row is dropped, reordered, or deduplicated. Fully empty rows are **kept** and counted (`ingest.blank_rows`); they surface as an issue in §8, not a silent deletion.
4. Physical types: `INTEGER → Int64`, `NUMERIC → Decimal(38,10)`, `FLOAT → Float64`, `BOOLEAN → Boolean`, `DATE → Date`, `DATETIME → Datetime[us, UTC]`, others `Utf8`.
5. Parquet writer settings are pinned (zstd level 3, 128 k-row groups, dictionary encoding on, statistics on) so output bytes are stable for a given library version; `content_sha256` is the hash of the file bytes. A logical fingerprint (`sha256` over the canonical row stream) is also recorded in `stage_runs.counts.data_fingerprint` for cross-library-version comparison.
6. A dataset with 0 data rows, or whose columns are all empty ⇒ `DATASET_EMPTY`; > `MAX_ROWS` ⇒ `DATASET_TOO_MANY_ROWS`; > `MAX_COLUMNS` ⇒ `DATASET_TOO_MANY_COLUMNS`.

---

# 6. Profiling

Runs in the `PROFILING` stage over the run's dataset version. Values that fail to parse for the column's `detected_type` are **excluded from numeric/date statistics** and counted in `parse_failures`.

## 6.1 Dataset-level (`dataset_profiles`)

| Field | Definition |
|---|---|
| `row_count`, `column_count` | Rows and columns of the version |
| `memory_bytes` | Polars `estimated_size()` of the fully materialized frame, or the sum over row groups when streamed (informational) |
| `duplicate_row_count` | Rows that are exact repeats of an earlier row: `n − n_unique_rows` (full-row hash, null-safe, §8.6) |
| `missing_cell_count` | Σ null cells over all columns |
| `missing_pct` | `100 · missing_cell_count / (row_count · column_count)`, stored `numeric(7,4)` |

## 6.2 Column-level (`dataset_columns`)

| Field | Definition |
|---|---|
| `null_count`, `null_pct` | Nulls (after null-token normalization); `100·null_count/row_count` |
| `unique_count`, `unique_pct` | Distinct non-null values; `100·unique_count/non_null_count` (so a fully unique column is 100 %) |
| `min`, `max` | Numeric/date: over parsed values; text: lexicographic min/max of values (truncated to 64 chars) |
| `mean` | Arithmetic mean (numeric only) |
| `median`, percentiles `p01,p05,p25,p75,p95,p99` | **Linear interpolation** between closest ranks (NumPy `method="linear"`, Polars `interpolation="linear"`): for `q`, position `h = (n−1)q`, value `x[⌊h⌋] + (h−⌊h⌋)(x[⌈h⌉] − x[⌊h⌋])` |
| `std` | **Sample** standard deviation (`ddof = 1`); `null` when `n < 2` |
| `skewness` | Adjusted Fisher–Pearson `G₁`; `null` when `n < 3` or std = 0 |
| `top_values` | Up to 20 `{v, n}` by count desc, then value asc (categorical/text/identifier ≤ 100 chars) |
| `avg_length` | Mean character length (text types) |
| `stats.null_tokens`, `stats.parse_rate`, `stats.storage_dtype`, `stats.is_date_only`, `stats.pct_suffix`, `stats.decimal_places_max` | Type-inference evidence (§5) |

Exact quantities (min, max, counts, sums) are computed exactly. **Approximate sketches** (e.g., HyperLogLog for distinct counts in columns with > 10 M distinct values) are allowed only for *display hints*, flagged `stats.approximate = true`, and are never used to produce a persisted metric or a quality score.

## 6.3 PII suspicion (`is_pii_suspected`)

A column is flagged when **any** holds: name matches `(^|_)(name|first_name|last_name|full_name|email|e_mail|phone|mobile|contact|address|street|zip|postcode|pincode|dob|birth|ssn|aadhaar|pan|passport)($|_)`; ≥ 30 % of sampled values (first 10,000 non-null) match an email regex, a phone regex (7–15 digits with optional `+`, spaces, dashes), or a government-ID shape; or a high-cardinality text column whose values look like person names (two capitalized tokens, ≥ 80 %). Flagged columns are excluded from LLM prompts and logs and masked in previews when `mask_pii_preview` is on (ARCHITECTURE §21). `CUSTOMER_ID`-role columns are **not** PII-flagged by default (they are pseudonymous keys) unless they match the email/phone patterns.

---

# 7. Semantic Column Detection

Implements PRD §23 and ARCHITECTURE §8.5: **deterministic rules first → optional LLM suggestion for ambiguous columns → deterministic validation → user-visible, editable mapping**. The mapping that drives analysis is always the validated one.

## 7.1 Matching vocabulary

Names are compared after the normalization in §5.3, as token lists (`unit_price` → `[unit, price]`). Synonym sets are static data shipped with the engine (`semantics/vocab/retail.yaml`), versioned with `PIPELINE_VERSION`.

| Role | Exact synonyms (whole normalized name) | Weak tokens |
|---|---|---|
| `CUSTOMER_ID` | `customer_id, cust_id, customerid, client_id, user_id, buyer_id, member_id, shopper_id, customer_no, customer_number, customer_code` | `customer, cust, client, buyer, member` |
| `TRANSACTION_ID` | `transaction_id, txn_id, order_id, invoice_no, invoice_number, invoice_id, receipt_id, receipt_no, bill_no, sale_id, order_number, order_no, invoice` | `transaction, txn, invoice, receipt, order` |
| `PRODUCT_ID` | `product_id, sku, stock_code, item_id, article_id, product_code, item_code, asin, upc, ean` | `sku, stock, article` |
| `PRODUCT_NAME` | `product_name, product, item_name, item, description, product_description, title, article_name` | `product, item, description, title` |
| `CATEGORY` | `category, product_category, item_category, department, product_type, category_name` | `category, department, type` |
| `QUANTITY` | `quantity, qty, units, units_sold, quantity_sold, pieces, items_sold, order_quantity` | `qty, quantity, units, pieces` |
| `PRICE` | `price, unit_price, price_per_unit, selling_price, sale_price, item_price, unitprice, rate` | `price, rate` |
| `REVENUE` | `revenue, sales, sales_amount, total_amount, total_price, net_sales, order_value, line_total, gmv, turnover, total_revenue, order_amount, net_amount, amount, total` | `revenue, sales, amount, total, gmv` |
| `DISCOUNT` | `discount, discount_pct, discount_percent, discount_amount, discount_rate, disc, markdown, promo_discount` | `discount, disc, markdown, promo` |
| `PURCHASE_DATE` | `purchase_date, order_date, transaction_date, invoice_date, sale_date, order_datetime, purchase_time, date, timestamp, invoicedate` | `date, time, timestamp, datetime` |
| `CUSTOMER_AGE` | `customer_age, age, buyer_age` | `age` |
| `GENDER` | `gender, sex, customer_gender` | `gender, sex` |
| `CITY` | `city, town, shipping_city, billing_city, customer_city` | `city, town` |
| `STATE` | `state, province, state_code, region, customer_state` | `state, province, region` |
| `COUNTRY` | `country, nation, country_code, ship_country, customer_country` | `country, nation` |
| `PAYMENT_METHOD` | `payment_method, payment_type, payment_mode, pay_method, payment, tender_type` | `payment, tender` |

`CUSTOMER_AGE` and `GENDER` are *descriptive* roles: they enable distribution views only and never block any module.

## 7.2 Scoring

For every (column `c`, role `r`) pair:

```text
N(c,r)  name score        1.00  normalized name ∈ exact(r)
                          0.85  some exact(r) synonym is a contiguous token run inside the name
                                (e.g. order_date_utc ⊃ order_date)
                          0.70  difflib.SequenceMatcher ratio ≥ 0.90 against an exact(r) synonym (typos)
                          0.55  a weak token of r appears in the name
                          0.00  otherwise
T(c,r)  type gate         1 if detected_type ∈ allowed(r) (table §7.4), else 0  (hard gate)
V(c,r)  value pattern     0..1 per §7.3 (uses only profile statistics, never raw values beyond samples)

confidence(c,r) = T(c,r) × ( 0.60·N(c,r) + 0.40·V(c,r) )
```

Consequences: a column with no name signal can reach at most 0.40 (never assigned); a weak-token name with a perfect value pattern reaches 0.73 (a *candidate*); an exact name with a mediocre value pattern (`V = 0.5`) still reaches 0.80 (accepted).

Special rule — **sole date column:** if exactly one column has type `DATE`/`DATETIME`, no other column claims `PURCHASE_DATE`, and its values fall in the plausible range (`[1990-01-01, as_of_date + 366 days]` for ≥ 95 % of values), assign `PURCHASE_DATE` with confidence `0.75` and note `sole_date_column`.

## 7.3 Value-pattern scores `V(c,r)`

| Role | `V = 1.0` when | `V` lower when |
|---|---|---|
| `CUSTOMER_ID` | `2 ≤ unique_count ≤ 0.9·rows` (customers repeat) | `0.6` if almost unique per row (one order per customer — plausible); `0` if `unique_count < 2` |
| `TRANSACTION_ID` | `unique_pct ≥ 50` and `null_pct ≤ 1` | `0.6` otherwise if `unique_count > 2` |
| `PRODUCT_ID` | `2 ≤ unique_count ≤ 0.9·rows` | `0.5` if nearly unique per row |
| `PRODUCT_NAME` | text/categorical, `avg_length ≥ 3`, `unique_count ≤ 0.5·rows` | `0.5` otherwise |
| `CATEGORY` | `CATEGORICAL`, `2 ≤ unique_count ≤ 200` | `0.7` for `TEXT` ≤ 200 distinct; else `0` |
| `QUANTITY` | integral values, ≥ 90 % positive, median ≤ 100, max ≤ 10,000 | `0.6` otherwise |
| `PRICE` | ≥ 95 % non-negative, median > 0 | `0.5` otherwise |
| `REVENUE` | numeric, ≥ 90 % non-negative, median > 0, right-skewed (`skewness > 0`) | `0.7` if not skewed |
| `DISCOUNT` | numeric, ≥ 90 % `≥ 0`, and (`max ≤ 100` or `max ≤ max(REVENUE candidate)`) | `0.5` otherwise |
| `PURCHASE_DATE` | ≥ 95 % in plausible range | `0.4` otherwise |
| `CUSTOMER_AGE` | integral, ≥ 95 % within `[0,120]`, median in `[10,90]` | `0.5` otherwise |
| `GENDER` | ≤ 6 distinct values and ≥ 90 % of values in `{m,f,male,female,man,woman,other,non-binary,nb,u,unknown}` | `0` otherwise |
| `COUNTRY` | ≥ 80 % of values in the bundled ISO-3166 names/alpha-2/alpha-3 table | `0.4` otherwise |
| `STATE` / `CITY` | categorical/text, `unique_count ≤ 100` (state) / `≤ 20,000` (city) | `0.5` otherwise |
| `PAYMENT_METHOD` | `CATEGORICAL`, `unique_count ≤ 20`; `+` all remain `1.0` if ≥ 40 % of values in `{cash, card, credit, debit, upi, wallet, netbanking, net banking, paypal, cod, cheque, emi, gift card}` | `0.6` if categorical ≤ 20 without token hits |

## 7.4 Allowed types per role (hard gate)

| Role | Allowed `detected_type` |
|---|---|
| `CUSTOMER_ID`, `TRANSACTION_ID`, `PRODUCT_ID` | `IDENTIFIER`, `INTEGER`, `CATEGORICAL`, `TEXT` |
| `PRODUCT_NAME`, `CATEGORY`, `GENDER`, `CITY`, `STATE`, `COUNTRY`, `PAYMENT_METHOD` | `CATEGORICAL`, `TEXT`, `IDENTIFIER` (CATEGORY/GENDER/PAYMENT_METHOD exclude `IDENTIFIER`) |
| `QUANTITY` | `INTEGER`, `NUMERIC`, `FLOAT` |
| `PRICE`, `REVENUE`, `DISCOUNT` | `INTEGER`, `NUMERIC`, `FLOAT` |
| `PURCHASE_DATE` | `DATE`, `DATETIME`; also `TEXT` whose **intended** type (stats) is date with `parse_rate ≥ 0.90` |
| `CUSTOMER_AGE` | `INTEGER`, `NUMERIC` |

## 7.5 Assignment and thresholds

1. Build all candidates with `confidence ≥ 0.45`.
2. Sort by `confidence` desc, then column `ordinal` asc, then role enum order (deterministic).
3. Greedily assign: a candidate is taken if its column and its role are both still free **and** `confidence ≥ 0.75` (source `RULE`, `semantic_validated = true` once §7.6 passes).
4. Candidates in `[0.45, 0.75)` are **not** assigned. They are stored in `dataset_columns.stats.candidate_roles = [{role, confidence}]`, offered to the optional LLM step (§7.7), and shown in the UI mapping editor as one-click suggestions.
5. A column with no assignment keeps `UNKNOWN`.

Confidence is stored in `semantic_confidence` (rounded to 4 decimals). A mapping change by the user sets `semantic_source = USER`, `semantic_validated = true`, `semantic_confidence = 1`.

## 7.6 Validation, derived settings, and grain

**Hard validation** (a failing assignment is reverted to `UNKNOWN` with a recorded reason; user overrides that fail return `MAPPING_INVALID`):

| Check | Rule |
|---|---|
| Type gate | §7.4 |
| One column per role | Enforced (also by DB unique index) |
| Coverage | A role-bearing column must have `null_pct ≤ 50` to count as **usable**; above that the column keeps its role but modules treat the role as *insufficiently populated* (§16.2) |
| Date plausibility | `PURCHASE_DATE`: ≥ 90 % parse success; ≥ 90 % in plausible range |
| Monetary non-degeneracy | `REVENUE`/`PRICE`: not all zero or constant (std > 0) |
| Cross-field sanity (warning, not a failure) | If `PRICE`, `QUANTITY`, `REVENUE` all mapped: share of rows with `|revenue − price·quantity| ≤ max(0.01, 1 % · |price·quantity|)` is stored as `mapping.revenue_consistency_ratio`; if < 0.80 a warning `REVENUE_NOT_PRICE_TIMES_QUANTITY` is raised (e.g., revenue includes tax/shipping/discount) |

**Derived mapping settings** (stored with the mapping, part of `mapping_hash`, editable by the user):

| Setting | Values | Inference |
|---|---|---|
| `revenue_basis` | `OBSERVED` · `DERIVED_GROSS` · `DERIVED_NET` | `OBSERVED` if `REVENUE` is mapped. Else `DERIVED_GROSS` (`price × quantity`) when `PRICE` and `QUANTITY` are mapped. `DERIVED_NET` only if the user sets `config.derived_revenue.apply_discount = true` and `discount_kind ≠ FLAG`. Derived revenue is always labeled "derived" in metrics, charts, and reports (ARCHITECTURE §8.8). |
| `discount_kind` | `RATIO` (0–1) · `PERCENT` (0–100) · `AMOUNT` (currency per line) · `FLAG` (0/1 only) | `FLAG` if values ⊆ `{0,1}` and name has no `pct/percent/rate`; `PERCENT` if name matches `pct|percent|%|rate` and `max ≤ 100`, or `pct_suffix`; `RATIO` if all values in `[0,1]` with fractional values; `PERCENT` if all in `[0,100]`, `max ≤ 100`, `median ≤ 50`; else `AMOUNT`. |
| `order_grain` | `LINE_ITEMS` · `ORDER_LEVEL` · `UNDEFINED` | `UNDEFINED` without `TRANSACTION_ID`. Else `LINE_ITEMS` if ≥ 2 % of rows share a `TRANSACTION_ID` with another row **and** within those groups rows are not all exact duplicates; else `ORDER_LEVEL`. |
| `frequency_basis` | `ORDERS` · `ROWS` | `ORDERS` if `TRANSACTION_ID` is mapped, else `ROWS` (§13.2). |

`discount_rate` (derived column, ratio 0–1, §10.2) is: `RATIO` → value; `PERCENT` → value/100; `AMOUNT` → `discount / (price·quantity)` when both are mapped and the gross > 0, otherwise `null`; `FLAG` → `null` (use `is_discounted`).

## 7.7 Optional LLM role suggestion

Allowed only when `project.settings.llm_enabled` and the gateway is available. Applies to columns that are `UNKNOWN` after §7.5 and have at least one candidate with confidence in `[0.45, 0.75)`.

| Aspect | Rule |
|---|---|
| Input | Normalized name, `detected_type`, profile statistics, up to 10 distinct sample values — **never** for `is_pii_suspected` columns, and never raw rows |
| Output | One enum value from the role list (or `UNKNOWN`) and a confidence in `[0,1]` |
| Acceptance | The suggestion is accepted only if it passes §7.6 validation **and** `V(c, role) ≥ 0.6` **and** the role is still unassigned |
| Persistence | `semantic_source = LLM_SUGGESTED`, `semantic_confidence = min(llm_confidence, 0.80)`, `semantic_validated = true` only after validation |
| Precedence | An LLM suggestion never displaces a `RULE` or `USER` assignment |
| Failure | Provider unavailable ⇒ skip silently (candidates remain visible); the run is unaffected (ARCHITECTURE §3) |

## 7.8 Mapping persistence and carry-forward

The mapping lives on `dataset_columns` per dataset version. When cleaning creates version *n+1*, the engine **carries the mapping forward by normalized column name**, preserving `source` and `confidence`, then re-runs §7.6 validation against the new version (types may have changed). Users therefore never re-map after cleaning unless validation now fails. Any change to a role, `revenue_basis`, `discount_kind`, or `order_grain` changes `mapping_hash` ⇒ new `run_key` (API §7.5).

---

# 8. Data Quality

Implements PRD §24–26, §35, §117. Computed in the `CLEANING` stage over the run's dataset version; results go to `data_quality_reports` and `quality_issues`. The exact methodology below is `methodology_version = "1.0"`.

## 8.1 Score structure

```text
overall = 0.30·Completeness + 0.20·Consistency + 0.25·Validity + 0.25·Uniqueness     (0–100, 2 decimals)

each dimension:   S_d = 100 − min(100,  k_d · P_d )
                  P_d = weighted mean *percentage* of affected cells/rows over the dimension's
                        applicable components (defined below)
sensitivity k_d:  Completeness 2 · Consistency 2 · Validity 3 · Uniqueness 10
```

Sensitivity makes a score move visibly for realistic problem rates: 5 % weighted missingness → Completeness 90; 5 % inconsistent cells → Consistency 90; 3 % invalid rows → Validity 91; 1 % duplicate rows → Uniqueness 90. Weights and sensitivities are stored on each report (`weights`, and `summary.sensitivity`); changing either bumps `methodology_version`.

| Band | Score | UI color (DESIGN §5.9) |
|---|---|---|
| Good | ≥ 85 | success |
| Fair | 70 – 84.99 | warning |
| Poor | < 70 | danger |

**Accuracy indicators** (PRD lists them as a dimension) are **reported but not scored** in methodology 1.0: without ground truth, "accuracy" can only be indicated, not measured. They are stored in `accuracy_indicators` (§8.7). See §24 (R-10).

## 8.2 Completeness

```text
P_comp = 100 · Σ_c ( w_c · m_c ) / Σ_c w_c        m_c = null_count_c / row_count   (0–1)
w_c = 3   for columns mapped to CUSTOMER_ID, TRANSACTION_ID, PRODUCT_ID, REVENUE, QUANTITY, PRICE, PURCHASE_DATE
    = 2   for other mapped roles
    = 1   for UNKNOWN columns
```

Columns that are 100 % null are included (they correctly lower the score) **and** raise a separate `MISSING_VALUES` issue with severity `CRITICAL`.

## 8.3 Consistency

Components apply only where their base is non-empty; `P_cons = 100 · Σ_j w_j f_j / Σ_{applicable} w_j` where `f_j` is the affected fraction.

| Component `j` | Weight | `f_j` (affected fraction) | Applicable when |
|---|---:|---|---|
| Type inconsistency | 3 | Unparsable non-null cells ÷ non-null cells, over columns with intended type ≠ storage type (§5.5 mixed columns) | ≥ 1 such column |
| Format inconsistency | 2 | Cells **not** in the dominant date/number format ÷ non-null cells, over date columns with mixed formats and numeric columns with mixed separator styles | ≥ 1 date or numeric column |
| Category variants | 2 | Rows whose value is a non-dominant variant of its normalized group ÷ non-null rows, over `CATEGORICAL` columns. Variant grouping key: NFKC, casefold, collapse whitespace, strip punctuation. Dominant variant = most frequent (ties: lexicographically smallest). | ≥ 1 categorical column |
| Header conflicts | 3 | Rows in order groups whose header-level fields (`CUSTOMER_ID`, `PURCHASE_DATE`, `PAYMENT_METHOD`, `COUNTRY`) disagree ÷ rows, under `LINE_ITEMS` grain | `order_grain = LINE_ITEMS` |

## 8.4 Validity

Rules are evaluated per row; `ρ_r = violating rows ÷ rows where the rule's columns are non-null`. `P_val = 100 · Σ_r w_r ρ_r / Σ_{applicable} w_r`. If no rule is applicable, `S_val = 100` and the report states `applicable_rules = 0`.

| Rule | Weight | Violation | Applicable when |
|---|---:|---|---|
| `VAL-PRICE-NEG` | 3 | `price < 0` | `PRICE` mapped |
| `VAL-QTY` | 2 | `quantity = 0`, or non-integer when the column is integral by type | `QUANTITY` mapped |
| `VAL-REV-SIGN` | 3 | `revenue < 0` **and** `quantity ≥ 0`, or `revenue > 0` **and** `quantity < 0` (sign mismatch). If `QUANTITY` is unmapped, negative revenue is treated as a refund/adjustment, **not** a violation | `REVENUE` and `QUANTITY` mapped |
| `VAL-DISC` | 2 | By `discount_kind`: `RATIO` outside `[0,1]`; `PERCENT` outside `[0,100]`; `AMOUNT < 0` or `> gross` when gross is known | `DISCOUNT` mapped, kind ≠ `FLAG` |
| `VAL-DATE` | 3 | `purchase_date > as_of_date` or `< 1990-01-01` | `PURCHASE_DATE` mapped |
| `VAL-AGE` | 2 | Outside `[0, 120]` | `CUSTOMER_AGE` mapped |
| `VAL-GENDER` | 1 | Not in the recognized gender token set (§7.3) | `GENDER` mapped |

Consistent negative quantity **and** negative revenue (returns) are valid and counted in the `refund_rows` indicator.

## 8.5 Issue types and handling states

`quality_issues.issue_type` values (DATABASE §6.6) and how the engine emits them:

| Issue type | Emitted when | Default `handling` | Severity |
|---|---|---|---|
| `MISSING_VALUES` | Column `null_pct > 0` | `DETECTED` if severity `LOW`, else `FLAGGED` | By band (§8.8) |
| `EXACT_DUPLICATES` | `duplicate_row_count > 0` | `DETECTED` | — |
| `DUPLICATE_IDENTIFIERS` | Conflicting identifier groups (§8.6) | `FLAGGED` | — |
| `NEAR_DUPLICATES` | Near-duplicate groups > 0 (§8.6) | `FLAGGED` | — |
| `OUTLIERS` | Column has outliers (§8.9) | `FLAGGED` (with `details.explanation`) | — |
| `INVALID_VALUES` | Any §8.4 rule with `X_r > 0` (rule id in `details.rule`) | `FLAGGED` | — |
| `TYPE_INCONSISTENCY` | Mixed-type column (§5.5) | `FLAGGED` | — |
| `FORMAT_INCONSISTENCY` | Mixed date/number formats or category variants | `FLAGGED` | — |
| `NEGATIVE_VALUES` | Negative `PRICE`/`QUANTITY` not explained by returns | `FLAGGED` | — |
| `FUTURE_DATES` | `purchase_date > as_of_date` | `FLAGGED` | — |

**Handling semantics (PRD §26):** `DETECTED` — found and counted; `FLAGGED` — individual records identified (a capped sample is stored at `sample_storage_key`) and surfaced for review; `REMOVED` — removed by a cleaning operation in an **ancestor version**.

**Lineage rows.** A quality report for version *n* also includes **synthesized issues** from `cleaning_operations` on its ancestors with `rows_affected > 0` (e.g., `REMOVE_EXACT_DUPLICATES` ⇒ an `EXACT_DUPLICATES` issue with `handling = REMOVED`, `what_changed = "Removed in version 2 (Duplicate Removal)."`). The *score* is always computed on version *n*'s own data; synthesized rows carry `details.synthesized = true` and never affect it. This is how the Issue log answers "what was wrong → what changed → why" (PRD §117).

Every issue fills: `what_was_wrong` (plain sentence with counts), `why` (templated impact statement), and `what_changed` (`null` unless `REMOVED`/lineage). Text is rendered from templates in `quality/templates.py`; counts are bound from computed values, never typed.

## 8.6 Duplicate detection

All keys are computed on the **canonicalized** row: strings NFC-normalized and trimmed, decimals as exact strings, dates ISO, nulls as a sentinel byte distinct from the empty string (null-safe equality: two nulls match).

| Kind | Algorithm |
|---|---|
| **Exact** | Hash all columns (xxh3-128 over the canonical byte row, stable library pinned). `duplicate_row_count = n − n_distinct_hashes`. The *kept* row in any later removal is the one with the smallest `line_id`. |
| **Duplicate identifiers** | Only for `TRANSACTION_ID`. `ORDER_LEVEL`: any `order_id` that appears more than once is a conflict group; affected rows = rows beyond the first per group. `LINE_ITEMS`: repeated `order_id` is normal; a **conflict group** is an `order_id` whose header-level fields (`CUSTOMER_ID`, `PURCHASE_DATE` date part, `PAYMENT_METHOD`, `COUNTRY`) are not all equal; affected rows = all rows in conflict groups. Exact duplicates are excluded from both. |
| **Near-duplicate** | Normalize each row (strings casefolded, whitespace collapsed, punctuation removed; decimals rounded to 2 places; datetimes truncated to the day; identifiers kept verbatim), hash the normalized row, and report groups of size ≥ 2 whose members are **not** all exact duplicates. This is O(n) and fully deterministic. Fuzzy (edit-distance) matching is out of scope for V1. Near-duplicates are **flagged, never auto-removed** (PRD §26). |

## 8.7 Accuracy indicators

Stored in `data_quality_reports.accuracy_indicators` (all integers unless noted, all unscored):

```json
{
  "negative_revenue_rows": 0, "refund_rows": 0, "zero_revenue_rows": 0,
  "future_date_rows": 12, "revenue_price_qty_mismatch_rows": 0,
  "revenue_consistency_ratio": 0.998, "outlier_columns": 3,
  "blank_rows": 0, "date_order_assumed": false
}
```

## 8.8 Missingness severity and patterns

Bands (config `thresholds.missingness`, defaults 5 / 20 / 50) use **upper-inclusive** boundaries on `null_pct`:

```text
null_pct ≤ low       → LOW          (0–5 %)
null_pct ≤ moderate  → MODERATE     (>5–20 %)
null_pct ≤ high      → HIGH         (>20–50 %)
null_pct >  high     → CRITICAL     (>50 %)
```

(PRD §25's "0–5 / 5–20" ranges overlap at the boundary; this resolves it: a value exactly on a boundary falls in the lower band.) A column with `null_pct = 0` produces no issue.

**Patterns** (for the heatmap, API `quality/missingness`): among columns with `null_count > 0` (max 20, chosen by `null_pct` desc then ordinal), compute (a) the pairwise **co-missing matrix** `P(A missing ∧ B missing) / P(A missing)` and (b) the **top 10 missing-masks** — distinct patterns of which of those columns are null together, with row counts, ordered by count desc then mask lexicographically.

## 8.9 Outlier detection

Eligible columns: numeric (`INTEGER`, `NUMERIC`, `FLOAT`) with `detected_type` not `IDENTIFIER`, not discrete (≤ 12 distinct), not constant, `n ≥ 20` non-null. Otherwise the column is recorded as *not assessed* with a reason (`too_few_values`, `discrete`, `constant`).

**Method selection per column** (recorded in `quality_issues.method`):

1. **`DOMAIN`** if the column has a domain rule (below) — applied *in addition* to the statistical method.
2. **`ZSCORE`** if `n ≥ 30` and `|skewness| < 1` (approximately symmetric): outlier if `|x − mean| / std > 3.0`.
3. **`IQR`** otherwise (default for skewed money/quantity data): outlier if `x < Q1 − 1.5·IQR` or `x > Q3 + 1.5·IQR` (Tukey fences; quartiles per §6.2). `config.thresholds.outliers.iqr_k` default `1.5`.

| Domain rule | Outlier when |
|---|---|
| `CUSTOMER_AGE` | outside `[0, 120]` |
| `QUANTITY` | `> 10,000` (configurable) |
| `PRICE` / `REVENUE` | `< 0` (also a validity rule; reported as `DOMAIN` outlier only when not explained by returns) |

**Behavior (PRD §35):** outliers are never removed by default. Each outlier issue is `handling = FLAGGED` and carries `details`:

```json
{
  "method": "IQR", "k": 1.5, "fences": {"lower": -412.5, "upper": 3187.5},
  "q1": 120.0, "q3": 2645.0, "iqr": 2525.0,
  "low_count": 0, "high_count": 1840, "max_value": "98500.0000000000",
  "explanation": "1,840 values are above 3,187.50 (Q3 + 1.5 × IQR). Large values are common in right-skewed revenue data and are not necessarily errors.",
  "user_decision": null
}
```

`explanation` is **always present** for flagged outliers — this is how the PRD's "Detected → Flagged → **Explained**" progression is represented without a fourth DB state (§24, R-01). A sample of the 100 most extreme rows (by distance from the nearer fence, then `line_id`) is written as Parquet at `sample_storage_key`. Outlier counts do **not** enter the quality score.

User actions in the UI map as: **Keep** / **Flag** record `details.user_decision` (`KEEP` / `FLAG`) as metadata (no analytics change); **Exclude from analysis** is a cleaning operation (§9.4) that creates a new version.
