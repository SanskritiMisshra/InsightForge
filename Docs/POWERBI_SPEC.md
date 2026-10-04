# InsightForge — Power BI Specification (POWERBI_SPEC.md)

**Version:** 1.0
**Model version:** `1` (recorded in `powerbi_models.model_version`)
**Status:** Authoritative for the Power BI-ready analytical model, DAX measures, dashboard specification, and delivery package
**Depends on:** `PRD.md` (§9.4, §55–57, §60, §65–66, §81, §96, §107, §112–114, §126), `ARCHITECTURE.md` (§8.8, §14.1, §14.4, §14.5), `DATABASE.md` (§6.9 `powerbi_models`, `metrics`), `API_SPEC.md` (§7.14), `SQL_SPEC.md` (§5, §10, §11), `DESIGN.md` (§2.4 palette, §5.17)
**Companion documents:** `ANALYTICS_SPEC.md` (definitions/thresholds), `REPORTING_SPEC.md`, `SECURITY.md`, `TESTING.md`

> **Authority rules.**
> 1. `SQL_SPEC.md` and the persisted `metrics` are the **numerical source of truth** (PRD §60, §96). This specification defines how the same numbers are *exposed in Power BI*; DAX measures must **reproduce** the persisted metrics, never redefine them. Any divergence is a defect, resolved before implementation continues (PRD §127).
> 2. V1 generates a **Power BI-ready package**. It does **not** publish to a Power BI tenant (PRD §9.4) and does **not** require producing a native `.pbix`/`.pbit` file (see §4.3 and ADR-020).

---

# 1. Purpose and Scope

## 1.1 Purpose

Turn a completed InsightForge analysis run into a **star-schema analytical model** that a user can load into Power BI Desktop in minutes, together with **verified DAX measures**, a **five-page dashboard specification**, a **branded theme**, and **provenance/reference values** that prove the Power BI numbers match the platform's.

## 1.2 In scope (V1)

| # | Deliverable | PRD |
|---|---|---|
| 1 | Star schema data tables (`fact_sales`, `dim_customer`, `dim_product`, `dim_date`, `dim_location`, `dim_payment` + supporting `dim_discount_band`) | §55 |
| 2 | Relationships, hierarchies, sort/format metadata, hidden-column guidance | §55 |
| 3 | DAX measures (Total Revenue, Total Orders, Total Quantity, Total Customers, AOV, Repeat Customer Rate, Revenue Growth, Revenue per Customer + supporting measures) | §56 |
| 4 | Dashboard specification: 5 pages with visuals, fields, filters, layout | §57 |
| 5 | Power Query (M) loaders with explicit types | §55 |
| 6 | Power BI theme (dark, matches `DESIGN.md` palette) | §98 |
| 7 | Manifest with provenance, checksums, and reference metric values for verification | §95, §96 |
| 8 | Availability handling: unavailable tables/measures/visuals/pages are explained, never silently dropped | §65–66 |
| 9 | Import instructions | §9.4 |

## 1.3 Out of scope (V1)

- Direct publishing/refresh in a Power BI tenant, workspace management, gateway/scheduled refresh (PRD §9.4). The architecture keeps a `PowerBIPublisher` adapter seam (`ARCHITECTURE.md` §14.4) for later.
- Real-time/DirectQuery models; incremental refresh; composite models; aggregations.
- Row-level security (V1 package is single-owner data).
- Calculation groups, field parameters, and custom visuals.
- Machine-learning visuals and forecasting.
- Native `.pbix` generation (optional enhancement, ADR-020).
- Map visuals requiring geocoding configuration (listed as optional in §8, page 5).

---

# 2. Principles

| # | Principle | Consequence |
|---|---|---|
| P1 | **One source of truth** | Fact/dimension data are exported from the same cleaned dataset version and derived relations (`customer_rfm`, `customer_segments`) used by SQL; measures are verified against persisted metrics |
| P2 | **Parity, not reinvention** | Each parity-scoped measure is bound to a `metric_name`; the **unfiltered** measure value must equal the metric (§9) |
| P3 | **Deterministic builds** | Same dataset version + same run config + same `model_version` ⇒ byte-identical data files (surrogate keys derived by sorted dense ranking) |
| P4 | **Nothing silently disappears** | Missing roles ⇒ affected tables/columns/measures/visuals are flagged `available: false` with a `reason` (PRD §65–66, §116) |
| P5 | **Precision honesty** | Power BI numeric types cannot hold `DECIMAL(38,10)`; the chosen Power BI type is recorded and parity tolerances are explicit (§6.6, §9.3) |
| P6 | **Association, not causation** | Discount/behavior visuals carry the standard caption (PRD §42) |
| P7 | **Privacy by default** | Identifier columns flagged as PII can be hashed or omitted; default is documented and visible (§12) |
| P8 | **Simple, conventional modeling** | Single fact, single-direction one-to-many relationships, no bidirectional filtering, no many-to-many |
| P9 | **Evidence-backed storytelling** | Dashboard KPI cards correspond to platform metrics so the same figure appears in the app, report, deck, and dashboard (PRD §60) |

---

# 3. Requirements

IDs are stable and referenced by tests (`TESTING.md`). Priority follows PRD §128.

## 3.1 Model requirements

| ID | Requirement | Priority |
|---|---|---|
| PBI-M-01 | The package SHALL contain a **star schema** with one fact table (`fact_sales`) and the dimensions `dim_customer`, `dim_product`, `dim_date`, `dim_location`, `dim_payment` (PRD §55), plus `dim_discount_band` when a discount column is usable | P1 |
| PBI-M-02 | Every relationship SHALL be **many-to-one** from the fact to a dimension with **single-direction** filtering (dimension → fact) | P1 |
| PBI-M-03 | Tables whose required roles are missing SHALL NOT be generated; their absence SHALL be recorded with a reason | P1 |
| PBI-M-04 | Surrogate keys SHALL be deterministic integers; the fact SHALL reference dimensions only by surrogate key | P1 |
| PBI-M-05 | Missing dimension attributes SHALL be represented by an explicit **Unknown member** (key `-1`) for product, location, payment, and discount band so that totals reconcile; customer and date use blank keys (§5.3) | P1 |
| PBI-M-06 | `dim_date` SHALL be a contiguous calendar covering whole calendar years of the data range, with completeness flags consistent with `SQL_SPEC.md` §5.5 | P1 |
| PBI-M-07 | The fact row count SHALL equal the cleaned dataset version's row count (no row dropped or duplicated) and `SUM(fact_sales.revenue)` SHALL equal metric `total_revenue` | P1 |
| PBI-M-08 | Monetary columns SHALL use the narrowest Power BI type that preserves the data exactly (Fixed decimal when scale ≤ 4 and precision fits; otherwise Decimal) and the choice SHALL be recorded | P1 |
| PBI-M-09 | Key, flag, and helper columns SHALL be marked hidden; sort-by-column, data categories, default summarization, hierarchies, and display folders SHALL be specified (§5.8) | P1 |
| PBI-M-10 | Identifier PII handling SHALL follow the project setting `powerbi_pii_mode` (`INCLUDE` default, `HASH`, `OMIT`) | P1 |

## 3.2 Measure requirements

| ID | Requirement | Priority |
|---|---|---|
| PBI-D-01 | The package SHALL include DAX for **Total Revenue, Total Orders, Total Quantity, Total Customers, Average Order Value, Repeat Customer Rate, Revenue Growth, Revenue per Customer** whenever their prerequisites exist (PRD §56) | P1 |
| PBI-D-02 | Each parity-scoped measure SHALL reproduce its bound platform metric under an **empty filter context** within the documented tolerance (§9.3) | P1 |
| PBI-D-03 | Measures SHALL use `DIVIDE` for ratios, variables for readability, and SHALL NOT contain hard-coded business values | P1 |
| PBI-D-04 | Measures whose prerequisites are missing SHALL NOT be emitted as executable DAX; `measures.dax` SHALL contain a commented placeholder with the reason | P1 |
| PBI-D-05 | Measure semantics (null handling, order grain, complete-period rules) SHALL match `SQL_SPEC.md` (§7.3 notes) | P1 |
| PBI-D-06 | Every measure SHALL have a display folder, format string, and description | P1 |

## 3.3 Dashboard requirements

| ID | Requirement | Priority |
|---|---|---|
| PBI-B-01 | The dashboard specification SHALL define the **five pages** of PRD §57 with visuals, fields, filters, and layout | P1 |
| PBI-B-02 | Pages/visuals depending on unavailable data SHALL be listed as unavailable with reasons | P1 |
| PBI-B-03 | Time visuals SHALL distinguish complete and partial periods | P1 |
| PBI-B-04 | Discount/behavior visuals SHALL display the association-not-causation caption | P1 |
| PBI-B-05 | The theme SHALL follow the `DESIGN.md` palette (dark, restrained, accent amber) and meet contrast requirements | P1 |
| PBI-B-06 | Each visual SHALL have a title and alt text; slicers SHALL be synchronized per §8.2 | P1 |

## 3.4 Package and process requirements

| ID | Requirement | Priority |
|---|---|---|
| PBI-P-01 | Generation SHALL run as a background job on the `generate` queue (PRD §63) and expose status via the API (`API_SPEC.md` §7.14) | P1 |
| PBI-P-02 | The package SHALL include a **manifest** with provenance (`dataset_version_id`, `run_id`, `pipeline_version`, `config_hash`, `model_version`), per-file SHA-256, row counts, and **reference values** for parity checks | P1 |
| PBI-P-03 | Generation SHALL be idempotent per run; regeneration with identical inputs SHALL produce the same package content (timestamps excepted) | P1 |
| PBI-P-04 | Download SHALL use short-lived presigned URLs and SHALL be audited (`powerbi.generated`, `powerbi.downloaded`) | P1 |
| PBI-P-05 | The package SHALL include import instructions and a verification checklist | P1 |
| PBI-P-06 | Optional: PBIP/TMDL project output and Tabular Editor script for one-step model creation | P2 |

---

# 4. Deliverable Package

## 4.1 Contents and layout

Delivered as `insightforge-powerbi-{project_slug}-{run_short_id}.zip` (stored at `powerbi/{owner_id}/{project_id}/{run_id}/{package}.zip`; `ARCHITECTURE.md` §10.1):

```text
insightforge-powerbi-retail-sales-analysis-01ja3x/
├── README.md                         # import steps + verification checklist (§11)
├── manifest.json                     # provenance, file checksums, row counts, reference values (§4.2)
├── data/
│   ├── fact_sales.csv
│   ├── dim_customer.csv
│   ├── dim_product.csv
│   ├── dim_date.csv
│   ├── dim_location.csv
│   ├── dim_payment.csv
│   └── dim_discount_band.csv         # only when discount is usable
├── data_parquet/                     # optional (setting powerbi_include_parquet): same tables, typed
├── model/
│   ├── schema.md                     # human-readable star schema documentation
│   ├── schema.json                   # machine-readable (same as powerbi_models.schema_def)
│   ├── relationships.json
│   ├── measures.dax                  # DAX definitions, display folders, format strings
│   ├── measures.json                 # same measures as structured data (powerbi_models.measures)
│   └── queries/
│       ├── 00_parameters.pq          # DataFolder parameter
│       ├── fact_sales.pq             # one M query per table (explicit types)
│       └── dim_*.pq
├── spec/
│   ├── dashboard_spec.md             # five-page dashboard specification (human-readable)
│   ├── dashboard_spec.json           # same as powerbi_models.dashboard_spec
│   └── dashboard_spec.pdf            # optional rendering
├── theme/
│   └── insightforge-dark.json        # Power BI report theme (§8.7)
└── verification/
    └── reference_values.json         # expected measure values from persisted metrics (§9)
```

Files whose prerequisites are missing are **omitted** and recorded in `manifest.json → unavailable[]` with reasons.

## 4.2 `manifest.json`

```json
{
  "package_version": 1,
  "model_version": "1",
  "generated_at": "2026-10-03T14:40:12Z",
  "provenance": {
    "project_id": "…", "run_id": "…", "dataset_id": "…",
    "dataset_version_id": "…", "dataset_version_number": 2,
    "dataset_content_sha256": "sha256:9c1d…e07",
    "pipeline_version": "1.0.3", "config_hash": "sha256:11a…", "mapping_hash": "sha256:7ab…",
    "domain_key": "retail", "currency": "INR",
    "revenue_is_derived": false, "frequency_basis": "ORDERS",
    "pii_mode": "INCLUDE", "reference_date": "2026-09-30",
    "data_min_date": "2024-01-01", "data_max_date": "2026-09-29"
  },
  "files": [
    { "path": "data/fact_sales.csv", "sha256": "sha256:…", "rows": 125106, "bytes": 38211934 }
  ],
  "tables": [
    { "name": "fact_sales", "rows": 125106, "grain": "one row per cleaned source row" }
  ],
  "unavailable": [
    { "kind": "TABLE", "name": "dim_discount_band", "reason": "A usable discount column was not detected.", "missing_roles": ["DISCOUNT"] }
  ],
  "reference_values_file": "verification/reference_values.json"
}
```

## 4.3 Native file generation (decision)

V1 delivers **data + M + DAX + relationships + theme + spec**, from which the user builds the model in Power BI Desktop (load queries, create five relationships, paste measures, apply the theme — ≈ 15 minutes, §11). This satisfies PRD §55 ("Power BI-ready analytical structure") and §9.4. Automated model-file generation (PBIP/TMDL or a Tabular Editor script) is a **P2 enhancement** (PBI-P-06). The `measures.json`/`relationships.json`/`schema.json` formats are designed so that a later generator can emit TMDL **without changing the model contract**.

---

# 5. Star Schema Specification

## 5.1 Diagram

```text
                       dim_date
                          │ (date_key)
 dim_customer ──────┐     │
   (customer_key)   │     │
                    ▼     ▼
 dim_product ─────► fact_sales ◄───── dim_location
   (product_key)       ▲   ▲            (location_key)
                       │   │
        dim_payment ───┘   └─── dim_discount_band
        (payment_key)           (discount_band_key)
```

**Grain of `fact_sales`: one row per cleaned source row (transaction line)**, identical to the `transactions` relation in `SQL_SPEC.md` §5.1. `transaction_id` is a **degenerate dimension** (kept on the fact).

## 5.2 Table availability

| Table | Built when | Otherwise |
|---|---|---|
| `fact_sales` | Revenue is available or derivable (`REVENUE`, or `PRICE` + `QUANTITY`) | **Model cannot be generated** → `409 MODULE_UNAVAILABLE` (API_SPEC §7.14) |
| `dim_customer` | `CUSTOMER_ID` mapped | Omitted; customer measures unavailable |
| `dim_product` | `PRODUCT_ID`, `PRODUCT_NAME`, or `CATEGORY` mapped | Omitted; product visuals unavailable |
| `dim_date` | `PURCHASE_DATE` mapped | Omitted; time visuals and growth measures unavailable |
| `dim_location` | Any of `COUNTRY`, `STATE`, `CITY` mapped | Omitted; geography page unavailable |
| `dim_payment` | `PAYMENT_METHOD` mapped | Omitted; payment visuals unavailable |
| `dim_discount_band` | `DISCOUNT` usable (SQL_SPEC §5.8) | Omitted; discount visuals unavailable |

Columns inside tables follow the same rule: a column whose source role is unmapped is **absent** (never filled with `NULL`).

## 5.3 Key and Unknown-member rules

| Rule | Detail |
|---|---|
| Surrogate keys | Positive integers assigned by **dense rank** of the sorted natural key (ascending, `NULL`s excluded), starting at `1`. Sorting uses binary (code-point) collation on normalized text, so results are deterministic across machines |
| `dim_date.date_key` | `YYYYMMDD` integer |
| Unknown member | Key `-1`, label `Unknown`, `is_unknown = true` — present in `dim_product`, `dim_location`, `dim_payment`, `dim_discount_band`; fact rows with a missing natural key point to `-1` |
| Customer / date | **No Unknown member.** Fact rows with a missing `customer_id` / `purchase_date` have a **blank (`NULL`)** `customer_key` / `date_key`. This keeps `DISTINCTCOUNT`-style customer logic and date intelligence correct; these rows still count in revenue totals (parity with `total_revenue`) and appear under "(Blank)" in visuals sliced by customer/date |
| Text attributes | `NULL` text attributes inside a dimension row are replaced with the literal `Unknown` (e.g., `category = 'Unknown'`) |
| Flags | `has_transaction_id` and `has_customer` booleans on the fact make parity-correct filters cheap and explicit |

## 5.4 `fact_sales`

| Column | Power BI type | Source | Notes |
|---|---|---|---|
| `line_id` | Whole number | Row ordinal in the dataset version Parquet (1-based) | Unique; deterministic |
| `transaction_id` | Text | `TRANSACTION_ID` | Degenerate dimension; may be blank |
| `has_transaction_id` | True/False | derived | `transaction_id IS NOT NULL` |
| `customer_key` | Whole number | `dim_customer` | Blank when `customer_id` missing |
| `has_customer` | True/False | derived | `customer_id IS NOT NULL` |
| `product_key` | Whole number | `dim_product` | `-1` when unknown |
| `date_key` | Whole number | `dim_date` | Blank when date missing |
| `location_key` | Whole number | `dim_location` | `-1` when unknown |
| `payment_key` | Whole number | `dim_payment` | `-1` when unknown |
| `discount_band_key` | Whole number | `dim_discount_band` | `-1` when discount missing |
| `quantity` | Fixed decimal / Decimal (§6.6) | `QUANTITY` | |
| `unit_price` | Fixed decimal / Decimal | `PRICE` | Only if mapped |
| `revenue` | Fixed decimal / Decimal | `REVENUE` or `price × quantity` | `revenue_is_derived` recorded in manifest |
| `discount_pct` | Decimal | `DISCOUNT` (percent, 0–100) | Only if usable |
| `order_line_count` | Whole number | lines per `transaction_id` | Blank when `transaction_id` blank; **never sum** (repeats per line) |
| `order_size_bucket` | Text | `'1'…'9'`, `'10+'` | Blank when `transaction_id` blank; bucket of `order_line_count` |

> `order_line_count` and `order_size_bucket` are **order-level attributes repeated on each line**. They are for slicing **distinct orders** (`Total Orders` by bucket), not for summation.

## 5.5 `dim_customer`

Grain: **one row per `customer_id`**.

| Column | Type | Notes |
|---|---|---|
| `customer_key` | Whole number | PK |
| `customer_id` | Text | Per PII mode (§12): raw, hashed, or **column omitted** |
| `first_purchase_date` / `last_purchase_date` | Date | Lifetime snapshot (`customers` relation) |
| `order_count` | Whole number | Lifetime orders (or rows when `frequency_basis = ROWS`) |
| `lifetime_revenue` | Fixed decimal / Decimal | Lifetime snapshot |
| `purchase_frequency_bucket` / `purchase_frequency_sort` | Text / Whole | `'1','2','3','4','5+'`; sort 1–5 |
| `customer_age` | Whole number | `MIN` per customer (deterministic); only if mapped |
| `gender` | Text | `MIN` per customer; only if mapped |
| `rfm_recency_days`, `rfm_frequency`, `rfm_monetary` | Whole / Whole / Decimal | From `customer_rfm` (SQL_SPEC §5.7) |
| `r_score`, `f_score`, `m_score` | Whole number | 1–5 |
| `rfm_score` | Text | e.g. `555` |
| `segment_code` / `segment` / `segment_sort` | Text / Text / Whole | `HIGH_VALUE → "High Value"`, `REGULAR → "Regular"`, `OCCASIONAL → "Occasional"`, `AT_RISK → "At Risk"`; sort 1–4 (SQL_SPEC §10.2 order) |

RFM/segment columns exist **only** when the RFM module is available (SQL_SPEC §5.7: `CUSTOMER_ID`, `PURCHASE_DATE`, revenue, and ≥ `rfm_min_customers` customers).

> **Snapshot semantics.** Lifetime, RFM, and segment columns are **static as of `reference_date`**. They do **not** recompute under date or category slicers. Visuals and measures that use them are labeled "as of {reference_date}" (§8).

## 5.6 `dim_product`

Grain: **one row per distinct (`product_natural_key`, `category`) combination** — so category totals match line-level category semantics in `SQL_SPEC.md` §10.4 even if a product appears under more than one category.

| Column | Type | Notes |
|---|---|---|
| `product_key` | Whole number | PK |
| `product_natural_key` | Text | `COALESCE(product_id, product_name)`; the identity used by product measures |
| `product_id` | Text | If mapped |
| `product_name` | Text | `MIN(product_name)` within the key/category group |
| `category` | Text | `Unknown` when missing |
| `is_unknown` | True/False | `true` only for the key `-1` member |

If only `CATEGORY` is mapped (no product identifier), the table has **category grain** (`product_natural_key` = category) and product-level visuals are marked unavailable.

## 5.7 `dim_date`, `dim_location`, `dim_payment`, `dim_discount_band`

**`dim_date`** — one row per calendar day from **Jan 1 of the first data year to Dec 31 of the last data year**:

| Column | Type | Definition |
|---|---|---|
| `date_key` | Whole | `YYYYMMDD` |
| `date` | Date | The day (PK; **marked as the date table's date column**) |
| `year`, `quarter`, `month`, `day` | Whole | Calendar parts |
| `quarter_label` | Text | `Q1 2026` |
| `month_name`, `month_short` | Text | `October`, `Oct` |
| `year_month` | Text | `2026-10` |
| `month_start`, `month_end`, `week_start` | Date | ISO week starts Monday |
| `iso_week` | Whole | ISO week number |
| `day_of_week` | Whole | 1 = Monday … 7 = Sunday |
| `day_name` | Text | `Monday` |
| `is_weekend` | True/False | |
| `month_sort` | Whole | `year*100 + month` |
| `in_data_range` | True/False | `data_min ≤ date ≤ data_max` |
| `month_is_complete` / `week_is_complete` / `year_is_complete` | True/False | Same definitions as `SQL_SPEC.md` §5.5 (relative to `data_min`/`data_max`) |

**`dim_location`** — grain: distinct (`country`, `state`, `city`) combinations present in the data plus the Unknown member.
Columns: `location_key`, `country`, `state`, `city`, `location_label` (most specific available level), `is_unknown`. Only mapped levels exist; unmapped levels are omitted.

**`dim_payment`** — `payment_key`, `payment_method`, `is_unknown`.

**`dim_discount_band`** — fixed bands aligned with `SQL_SPEC.md` §10.7:

| `discount_band_key` | `discount_band` | `band_order` | Rule (`discount_pct`) |
|---|---|---|---|
| 1 | `0` | 1 | `= 0` |
| 2 | `(0,10]` | 2 | `> 0 and ≤ 10` |
| 3 | `(10,20]` | 3 | `> 10 and ≤ 20` |
| 4 | `(20,30]` | 4 | `> 20 and ≤ 30` |
| 5 | `>30` | 5 | `> 30` |
| -1 | `Unknown` | 6 | missing |

> `dim_discount_band` is a **supporting dimension added to the PRD §55 list** because PRD §42/§57 require discount-level analysis; it is documented as an extension (ADR-021).

## 5.8 Relationships, hierarchies, and metadata

**Relationships** (all many-to-one, single-direction dim → fact, active; `Assume referential integrity` = off):

| From (many) | To (one) | Notes |
|---|---|---|
| `fact_sales[customer_key]` | `dim_customer[customer_key]` | blank keys allowed |
| `fact_sales[product_key]` | `dim_product[product_key]` | |
| `fact_sales[date_key]` | `dim_date[date_key]` | blank keys allowed |
| `fact_sales[location_key]` | `dim_location[location_key]` | |
| `fact_sales[payment_key]` | `dim_payment[payment_key]` | |
| `fact_sales[discount_band_key]` | `dim_discount_band[discount_band_key]` | |

`relationships.json`:
```json
[
  { "from": "fact_sales.customer_key", "to": "dim_customer.customer_key", "cardinality": "MANY_TO_ONE", "cross_filter": "SINGLE", "active": true }
]
```

**Hierarchies**

| Table | Name | Levels |
|---|---|---|
| `dim_date` | Date Hierarchy | `year → quarter_label → month_name → date` |
| `dim_location` | Location | `country → state → city` (mapped levels only) |
| `dim_product` | Product | `category → product_name` |

**Column metadata**

| Concern | Rule |
|---|---|
| Hidden | All `*_key` columns, `line_id`, `has_*` flags, `*_sort`, `month_sort`, `band_order`, `order_line_count`, `is_unknown`, `date_key` (unless needed) |
| Sort by column | `month_name` ← `month`; `month_short` ← `month`; `year_month` ← `month_sort`; `segment` ← `segment_sort`; `purchase_frequency_bucket` ← `purchase_frequency_sort`; `discount_band` ← `band_order`; `day_name` ← `day_of_week`; `order_size_bucket` ← helper `order_size_sort` (added to fact when needed) |
| Data categories | `country` → Country/Region; `state` → State or Province; `city` → City |
| Default summarization | **None** for keys, scores, codes, and years; **Sum** only for `revenue`, `quantity` (not used directly; measures preferred) |
| Format | Currency columns use the project currency symbol; counts `#,##0`; percent `0.0%` |
| Display folders | Defined in §7 |
| Date table | `dim_date` marked as date table on `date` |

---

# 6. Data Generation Rules

## 6.1 Inputs (all read-only, all pinned to the run)

| Input | Source |
|---|---|
| Cleaned dataset version | Parquet at `dataset_versions.storage_key`; **sha256 verified** against `content_sha256` before use |
| Validated semantic mapping | `dataset_columns` for that version (`mapping_hash` from the run) |
| Derived customer relations | `customers`, `customer_rfm`, `customer_segments` built by the **same SQL definitions** as `SQL_SPEC.md` §5.3, §5.7 (executed in the SQL sandbox; no separate re-implementation) |
| Run parameters | `run_params` (`reference_date`, `currency`, `revenue_is_derived`, `frequency_basis`) |
| Persisted metrics | `metrics` for the run (used only for `reference_values.json`) |

The builder (`analytics_engine/powerbi`) is a **pure function** of these inputs (`ARCHITECTURE.md` §8.1). It never re-computes business metrics for display; it exports **data** and **definitions**.

## 6.2 Build steps

```text
1. Verify run is COMPLETED and dataset version hash matches
2. Resolve availability (tables/columns/measures/pages) from mapping + module availability
3. Build dimensions (sorted natural keys → dense-rank surrogate keys; Unknown members)
4. Build fact_sales (row-preserving join of keys; derived flags/order attributes)
5. Reconcile: row counts, SUM(revenue), distinct-key integrity, no orphan keys (except documented blank customer/date keys)
6. Write CSV (and optional Parquet), compute checksums
7. Generate M queries, relationships, measures, schema, dashboard spec, theme, README
8. Generate reference_values.json from persisted metrics
9. Assemble ZIP with normalized timestamps; compute package checksum
10. Persist powerbi_models row + object; emit audit event + notification
```

Step 5 failures abort generation with `error_code = POWERBI_RECONCILIATION_FAILED` (internal defect; user sees a generic generation failure with retry).

## 6.3 Determinism rules

- Stable sort with binary collation for keys; stable row order in `fact_sales` = ascending `line_id`.
- ZIP entries sorted by path, timestamps fixed (`1980-01-01`), compression level fixed, so identical inputs yield **byte-identical** archives (apart from `manifest.generated_at`, which is excluded from the content hash used for idempotency).
- No use of wall-clock time, randomness, or environment-dependent formatting in data files.

## 6.4 CSV format contract

| Aspect | Rule |
|---|---|
| Encoding | UTF-8 (no BOM) |
| Delimiter / quoting | `,` and RFC 4180 quoting; embedded quotes doubled; `\n` line endings |
| Header | First row, exact column names |
| Dates / timestamps | `YYYY-MM-DD`; timestamps ISO-8601 UTC |
| Booleans | `true` / `false` |
| Numbers | `.` decimal separator, no thousands separators, no scientific notation, minimal trailing zeros removed only for integers (decimals keep their stored scale) |
| NULL | Empty field |
| Formula safety | Text cells beginning with `=`, `+`, `-`, `@` are prefixed with `'` **only in exports intended for spreadsheets**; the Power BI package marks columns as text types in M, and the prefix is applied to text columns for consistent handling when users open files in Excel (documented in README) |

## 6.5 Parquet (optional)

When `powerbi_include_parquet = true`, typed Parquet copies are added under `data_parquet/` with identical column names and the Power BI-compatible physical types (`DECIMAL(19,4)` or `DOUBLE` per §6.6, `INT32/INT64`, `DATE`, `BOOLEAN`, `STRING`). M queries for Parquet use `Parquet.Document`. CSV remains the default (broadest compatibility).

## 6.6 Numeric type selection (PBI-M-08)

Power BI's **Fixed decimal number** holds up to 19 significant digits with 4 decimals; **Decimal number** is IEEE double (~15 significant digits). The builder inspects each monetary/quantity column in the version:

| Condition | Power BI type | Parity implications |
|---|---|---|
| Max scale ≤ 4 **and** max |value| < 10¹⁵ | **Fixed decimal number** | Exact; sums exact |
| Otherwise | **Decimal number** (double) | Tiny floating-point differences possible; tolerance applies (§9.3) |

The decision per column is recorded in `schema.json` (`power_bi_type`) and in `manifest.json`. Raw values in CSV keep full stored precision regardless; Power Query typing determines the model type.

---

# 7. DAX Measures

## 7.1 Conventions

- Measure names use Title Case with spaces (user-facing); table/column references use the **technical names** from §5.
- Currency symbol in format strings derives from `project.currency` (`INR → ₹`, `USD → $`, `EUR → €`, `GBP → £`; otherwise the ISO code as a prefix). **Indian digit grouping (₹84.20L / 1,24,500) is a regional/formatting concern**: Power BI format strings follow the viewer's locale; the package documents a locale setting (`en-IN`) in the README instead of encoding grouping in format strings (PRD §112, §114).
- All ratios use `DIVIDE`; unit-less ratios display as `0.0%`.
- **Parity scope:** the measure's value in an **unfiltered** model (no slicers, no visual filters, grand total) equals the bound metric. Contextual measures (marked *contextual*) are for visuals and carry no parity guarantee.
- Variables (`VAR`) are used for clarity and to avoid repeated evaluation.

## 7.2 Required measures (PRD §56)

### Sales

```dax
Total Revenue =
SUM ( fact_sales[revenue] )
```
*Format:* currency · *Folder:* Sales · *Requires:* `fact_sales[revenue]` · *Parity:* `total_revenue`

```dax
Total Orders =
DISTINCTCOUNTNOBLANK ( fact_sales[transaction_id] )
```
*Format:* `#,##0` · *Folder:* Sales · *Requires:* `TRANSACTION_ID` · *Parity:* `total_orders`
> `DISTINCTCOUNTNOBLANK` mirrors SQL `COUNT(DISTINCT transaction_id)`, which ignores `NULL`. (`DISTINCTCOUNT` would count the blank as a value and break parity.)

```dax
Total Quantity =
SUM ( fact_sales[quantity] )
```
*Format:* `#,##0.##` · *Folder:* Sales · *Requires:* `QUANTITY` · *Parity:* `total_quantity`

```dax
Average Order Value =
DIVIDE (
    CALCULATE ( [Total Revenue], fact_sales[has_transaction_id] = TRUE () ),
    [Total Orders]
)
```
*Format:* currency · *Folder:* Sales · *Requires:* `TRANSACTION_ID`, revenue · *Parity:* `average_order_value`
> Numerator restricts to rows that belong to an order (`has_transaction_id`), matching `orders` in `SQL_SPEC.md` §5.2 (which excludes `NULL` `transaction_id`).

```dax
Revenue per Customer =
DIVIDE (
    CALCULATE ( [Total Revenue], fact_sales[has_customer] = TRUE () ),
    [Total Customers]
)
```
*Format:* currency · *Folder:* Customers · *Requires:* `CUSTOMER_ID`, revenue · *Parity:* `avg_revenue_per_customer` (= `avg_customer_revenue`)

```dax
Revenue Growth =
VAR LatestMonth =
    CALCULATE (
        MAX ( dim_date[month_start] ),
        ALL ( dim_date ),
        dim_date[month_is_complete] = TRUE ()
    )
VAR PreviousMonth = EDATE ( LatestMonth, -1 )
VAR PreviousComplete =
    CALCULATE (
        COUNTROWS ( dim_date ),
        ALL ( dim_date ),
        dim_date[month_start] = PreviousMonth,
        dim_date[month_is_complete] = TRUE ()
    ) > 0
VAR CurrentRevenue =
    CALCULATE ( COALESCE ( [Total Revenue], 0 ), ALL ( dim_date ), dim_date[month_start] = LatestMonth )
VAR PreviousRevenue =
    CALCULATE ( COALESCE ( [Total Revenue], 0 ), ALL ( dim_date ), dim_date[month_start] = PreviousMonth )
RETURN
    IF (
        NOT ISBLANK ( LatestMonth ) && PreviousComplete,
        DIVIDE ( CurrentRevenue - PreviousRevenue, PreviousRevenue )
    )
```
*Format:* `0.0%` · *Folder:* Sales · *Requires:* `PURCHASE_DATE`, revenue · *Parity:* `revenue_growth`
> Implements `sales_growth_latest_period` (SQL_SPEC §10.1): **latest complete month vs the immediately preceding complete month**; blank (not `0`) when two consecutive complete months do not exist; months with no sales count as `0` revenue. `ALL ( dim_date )` removes **date** filters only; other slicers (e.g., category) still apply — intended for "growth within a segment", and parity is defined for the unfiltered model.

```dax
Order Growth =
VAR LatestMonth =
    CALCULATE ( MAX ( dim_date[month_start] ), ALL ( dim_date ), dim_date[month_is_complete] = TRUE () )
VAR PreviousMonth = EDATE ( LatestMonth, -1 )
VAR PreviousComplete =
    CALCULATE ( COUNTROWS ( dim_date ), ALL ( dim_date ),
                dim_date[month_start] = PreviousMonth, dim_date[month_is_complete] = TRUE () ) > 0
VAR CurrentOrders =
    CALCULATE ( COALESCE ( [Total Orders], 0 ), ALL ( dim_date ), dim_date[month_start] = LatestMonth )
VAR PreviousOrders =
    CALCULATE ( COALESCE ( [Total Orders], 0 ), ALL ( dim_date ), dim_date[month_start] = PreviousMonth )
RETURN
    IF ( NOT ISBLANK ( LatestMonth ) && PreviousComplete,
         DIVIDE ( CurrentOrders - PreviousOrders, PreviousOrders ) )
```
*Format:* `0.0%` · *Folder:* Sales · *Requires:* `PURCHASE_DATE`, `TRANSACTION_ID` · *Parity:* `order_growth`

### Customers

```dax
Total Customers =
DISTINCTCOUNTNOBLANK ( fact_sales[customer_key] )
```
*Format:* `#,##0` · *Folder:* Customers · *Requires:* `CUSTOMER_ID` · *Parity:* `total_customers`

```dax
Repeat Customer Rate =
VAR Customers =
    FILTER ( VALUES ( fact_sales[customer_key] ), NOT ISBLANK ( fact_sales[customer_key] ) )
VAR RepeatCustomers =
    COUNTROWS (
        FILTER (
            Customers,
            CALCULATE ( DISTINCTCOUNTNOBLANK ( fact_sales[transaction_id] ) ) >= 2
        )
    )
RETURN
    DIVIDE ( RepeatCustomers, COUNTROWS ( Customers ) )
```
*Format:* `0.0%` · *Folder:* Customers · *Requires:* `CUSTOMER_ID`, `TRANSACTION_ID` · *Parity:* `repeat_purchase_rate`
> When `frequency_basis = ROWS` (no `TRANSACTION_ID`), the builder emits the variant that replaces `DISTINCTCOUNTNOBLANK ( fact_sales[transaction_id] )` with `COUNTROWS ( fact_sales )` and labels the measure "Repeat Customer Rate (by rows)". Within a date/category filter the measure answers "repeat **within the selected context**" (contextual behavior); parity is defined unfiltered.

## 7.3 Supporting measures

### Customers (continued)

```dax
Orders per Customer =
VAR Customers =
    FILTER ( VALUES ( fact_sales[customer_key] ), NOT ISBLANK ( fact_sales[customer_key] ) )
RETURN
    DIVIDE (
        SUMX ( Customers, CALCULATE ( DISTINCTCOUNTNOBLANK ( fact_sales[transaction_id] ) ) ),
        COUNTROWS ( Customers )
    )
```
*Parity:* `avg_orders_per_customer` · *Requires:* `CUSTOMER_ID`, `TRANSACTION_ID`

```dax
New Customers =
VAR MonthStart = SELECTEDVALUE ( dim_date[month_start] )
RETURN
    IF (
        NOT ISBLANK ( MonthStart ),
        CALCULATE (
            DISTINCTCOUNTNOBLANK ( fact_sales[customer_key] ),
            FILTER ( ALL ( dim_customer[first_purchase_date] ), dim_customer[first_purchase_date] >= MonthStart )
        )
    )

Returning Customers =
VAR MonthStart = SELECTEDVALUE ( dim_date[month_start] )
RETURN
    IF (
        NOT ISBLANK ( MonthStart ),
        CALCULATE (
            DISTINCTCOUNTNOBLANK ( fact_sales[customer_key] ),
            FILTER ( ALL ( dim_customer[first_purchase_date] ), dim_customer[first_purchase_date] < MonthStart )
        )
    )
```
*Contextual* (single month in context; matches `cust_new_vs_returning_monthly`). **Caveat shown in the dashboard:** the dataset's first month overstates "new" customers (history before the data start is unknown), so headline KPIs exclude it (see `New Customers (Headline)` below).

```dax
New Customers (Headline) =
VAR LatestMonth =
    CALCULATE ( MAX ( dim_date[month_start] ), ALL ( dim_date ), dim_date[month_is_complete] = TRUE () )
VAR FirstDataMonth =
    CALCULATE ( MIN ( dim_date[month_start] ), ALL ( dim_date ), dim_date[in_data_range] = TRUE () )
RETURN
    IF (
        NOT ISBLANK ( LatestMonth ) && LatestMonth > FirstDataMonth,
        CALCULATE (
            DISTINCTCOUNTNOBLANK ( fact_sales[customer_key] ),
            ALL ( dim_date ),
            dim_date[month_start] = LatestMonth,
            FILTER ( ALL ( dim_customer[first_purchase_date] ), dim_customer[first_purchase_date] >= LatestMonth )
        )
    )
```
*Parity:* `new_customers`. `Returning Customers (Headline)` is defined symmetrically (`first_purchase_date < LatestMonth`) → parity `returning_customers`. Headline rules (latest complete month, excluding the first data month) are those of `SQL_SPEC.md` §11.3 and `ANALYTICS_SPEC.md`.

```dax
Segment Customer Share =
DIVIDE ( [Total Customers], CALCULATE ( [Total Customers], ALL ( dim_customer[segment] ) ) )

Segment Revenue Share =
DIVIDE (
    [Total Revenue],
    CALCULATE ( [Total Revenue], ALL ( dim_customer[segment] ), fact_sales[has_customer] = TRUE () )
)
```
*Parity (per segment):* `segment_customer_share`, `segment_revenue_share` · *Requires:* RFM availability · *Evidence example:* High Value segment ≈ 51.7% of revenue vs 18.0% of customers (PRD §50 example is illustrative).

```dax
Avg Recency (days) = AVERAGE ( dim_customer[rfm_recency_days] )
Avg Frequency      = AVERAGE ( dim_customer[rfm_frequency] )
Avg Monetary       = AVERAGE ( dim_customer[rfm_monetary] )
```
*Snapshot* (as of `reference_date`); respect customer-dimension filters only.

### Purchase behavior

```dax
Average Lines per Order =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_sales ), fact_sales[has_transaction_id] = TRUE () ),
    [Total Orders]
)

Average Basket Quantity =
DIVIDE (
    CALCULATE ( [Total Quantity], fact_sales[has_transaction_id] = TRUE () ),
    [Total Orders]
)
```
*Parity:* `avg_lines_per_order`, `avg_basket_quantity` (`beh_basket_summary`).

### Products and categories

```dax
Product Revenue Share =
DIVIDE (
    [Total Revenue],
    CALCULATE ( [Total Revenue], ALL ( dim_product ), dim_product[is_unknown] = FALSE () )
)

Category Revenue Share =
DIVIDE (
    [Total Revenue],
    CALCULATE ( [Total Revenue], ALL ( dim_product ), dim_product[category] <> "Unknown" )
)
```
*Parity:* `product_revenue_share`, `category_revenue_share`. Denominators exclude unclassified revenue exactly as the SQL templates do; the **Unknown** bar equals metric `revenue_unclassified` (reconciliation, SQL_SPEC §10.4).

### Payment, discount, geography

```dax
Payment Revenue Share =
DIVIDE ( [Total Revenue],
         CALCULATE ( [Total Revenue], ALL ( dim_payment ), dim_payment[is_unknown] = FALSE () ) )

Country Revenue Share =
DIVIDE ( [Total Revenue],
         CALCULATE ( [Total Revenue], ALL ( dim_location ), dim_location[country] <> "Unknown" ) )

State Revenue Share =
DIVIDE ( [Total Revenue],
         CALCULATE ( [Total Revenue], ALL ( dim_location ), dim_location[state] <> "Unknown" ) )

City Revenue Share =
DIVIDE ( [Total Revenue],
         CALCULATE ( [Total Revenue], ALL ( dim_location ), dim_location[city] <> "Unknown" ) )
```
Discount-band analysis uses the base measures (`Total Revenue`, `Total Orders`, `Average Order Value`) sliced by `dim_discount_band[discount_band]`. **There is no DAX correlation measure**: the discount–revenue association (`discount_revenue_correlation`) is a platform metric shown in the app/report and as a static reference value; it is **not** recomputed in Power BI (P6).

### Time (contextual — for visuals)

```dax
Revenue (Complete Months) =
CALCULATE ( [Total Revenue], dim_date[month_is_complete] = TRUE () )

Revenue (Partial Months) =
CALCULATE ( [Total Revenue], dim_date[month_is_complete] = FALSE (), dim_date[in_data_range] = TRUE () )

Revenue MoM % =
VAR Previous = CALCULATE ( [Total Revenue], DATEADD ( dim_date[date], -1, MONTH ) )
RETURN IF ( NOT ISBLANK ( Previous ), DIVIDE ( [Total Revenue] - Previous, Previous ) )

Revenue YoY % =
VAR PreviousYear = CALCULATE ( [Total Revenue], SAMEPERIODLASTYEAR ( dim_date[date] ) )
RETURN IF ( NOT ISBLANK ( PreviousYear ), DIVIDE ( [Total Revenue] - PreviousYear, PreviousYear ) )
```
*Contextual;* MoM/YoY in visuals should be filtered to complete months (page-level or visual-level filter `month_is_complete = TRUE`). Series parity against `time_mom_growth` / `time_yoy_growth` is verified per month by the Level-1 evaluator (§9.2).

## 7.4 Measure catalog (summary)

| Measure | Folder | Requires (roles/tables) | Parity metric | Scope |
|---|---|---|---|---|
| Total Revenue | Sales | revenue | `total_revenue` | Parity |
| Total Orders | Sales | `TRANSACTION_ID` | `total_orders` | Parity |
| Total Quantity | Sales | `QUANTITY` | `total_quantity` | Parity |
| Average Order Value | Sales | `TRANSACTION_ID`, revenue | `average_order_value` | Parity |
| Revenue Growth | Sales | `PURCHASE_DATE`, revenue | `revenue_growth` | Parity |
| Order Growth | Sales | `PURCHASE_DATE`, `TRANSACTION_ID` | `order_growth` | Parity |
| Total Customers | Customers | `CUSTOMER_ID` | `total_customers` | Parity |
| Revenue per Customer | Customers | `CUSTOMER_ID`, revenue | `avg_revenue_per_customer` | Parity |
| Repeat Customer Rate | Customers | `CUSTOMER_ID`, `TRANSACTION_ID` | `repeat_purchase_rate` | Parity |
| Orders per Customer | Customers | `CUSTOMER_ID`, `TRANSACTION_ID` | `avg_orders_per_customer` | Parity |
| New / Returning Customers (Headline) | Customers | `CUSTOMER_ID`, `PURCHASE_DATE` | `new_customers`, `returning_customers` | Parity |
| New / Returning Customers | Customers | same | monthly series | Contextual |
| Segment Customer/Revenue Share | Customers | RFM | `segment_customer_share`, `segment_revenue_share` | Parity (per segment) |
| Avg Recency / Frequency / Monetary | Customers | RFM | — (snapshot) | Contextual |
| Average Lines per Order / Basket Quantity | Purchase Behavior | `TRANSACTION_ID`, `QUANTITY` | `avg_lines_per_order`, `avg_basket_quantity` | Parity |
| Product / Category Revenue Share | Products | product/category + revenue | `product_revenue_share`, `category_revenue_share` | Parity (per member) |
| Payment Revenue Share | Purchase Behavior | `PAYMENT_METHOD` | `revenue_by_payment_method` share | Parity (per member) |
| Country/State/City Revenue Share | Geography | location roles | `revenue_by_country/state/city` share | Parity (per member) |
| Revenue (Complete/Partial Months), MoM %, YoY % | Time | `PURCHASE_DATE` | `revenue_monthly`, `mom_growth`, `yoy_growth` series | Contextual (series parity via evaluator) |

## 7.5 `measures.json` entry

```json
{
  "name": "Average Order Value",
  "folder": "Sales",
  "dax": "DIVIDE ( CALCULATE ( [Total Revenue], fact_sales[has_transaction_id] = TRUE () ), [Total Orders] )",
  "format": "currency",
  "description": "Revenue per order. Matches platform metric average_order_value (unfiltered).",
  "requires": { "roles": ["TRANSACTION_ID"], "tables": ["fact_sales"] },
  "parity": { "metric_name": "average_order_value", "scope": "UNFILTERED", "tolerance": { "abs": 0.005, "rel": 1e-9 } },
  "available": true,
  "reason": null
}
```
Unavailable measures carry `available: false` and `reason` (e.g., *"A customer identifier is required."*) and appear in `measures.dax` as a comment:

```dax
// UNAVAILABLE: Repeat Customer Rate — A customer identifier is required.
```

---

# 8. Dashboard Specification

Canvas: **16:9, 1280 × 720 px**, 12-column grid (80 px margins ≈ 24 px gutters); page background `#0B0D10`; cards `#14181D` with 1 px `#2A313B` border, radius 8 px (DESIGN.md §2). Fonts: **Segoe UI** (available in Power BI Desktop by default; Inter is used by the web app only). Maximum **8 visuals per page**; numbers use tabular figures where the font supports them.

## 8.1 Page overview

| # | Page | PRD §57 | Required for page to be generated |
|---|---|---|---|
| 1 | Executive Overview | Page 1 | `fact_sales` (revenue) — always when model exists |
| 2 | Customer Analytics | Page 2 | `dim_customer` |
| 3 | Product Analytics | Page 3 | `dim_product` |
| 4 | Purchase Behavior | Page 4 | any of `dim_discount_band`, `dim_payment`, order attributes, `dim_customer` frequency bucket |
| 5 | Geography | Page 5 | `dim_location` |

Pages with missing prerequisites are **listed as unavailable with reasons** (dashboard_spec.json `available: false`); individual visuals within a page can also be unavailable while the page remains.

## 8.2 Global elements

| Element | Spec |
|---|---|
| Header strip | Page title (left), "Dataset v{n} · {run_short_id} · as of {reference_date}" (right) — text box populated from manifest at import time (documented manual step) |
| Navigation | Page navigator (buttons) at top; active page highlighted with amber underline |
| Slicers (synced across pages 1–5 unless noted) | **Date** (`dim_date[date]` between, 24 px high, top-left) · **Category** (`dim_product[category]` dropdown, pages 1, 3, 4) · **Country** (`dim_location[country]` dropdown, pages 1, 5) · **Customer segment** (`dim_customer[segment]` dropdown, pages 1, 2, 4) |
| Reset | "Clear filters" button using a bookmark |
| Interactions | Default cross-filtering; KPI cards are **not** filtered by their own page's slicers when labeled "All time" (none in V1 — all KPIs respond to slicers) |
| Caption | Footer note on pages 3–4: "Figures describe observed associations in the data; they do not establish causes." (PRD §42) |
| Alt text | Every visual: purpose + key fields (accessibility, PBI-B-06) |
| Tab order | Header → slicers → KPIs → charts left-to-right/top-to-bottom |

**Slicer note:** parity measures (`Revenue Growth`, headline customers) intentionally ignore **date** filters; with a date slicer applied they continue to report the **latest complete month** of the whole dataset. KPI card subtitles state this ("Latest complete month vs previous").

## 8.3 Page 1 — Executive Overview

```text
┌───────────────────────────────────────────────────────────────────────────────┐
│ Executive Overview                           Dataset v2 · run 01ja3x · 2026‑09‑30│
│ [Date ▾] [Category ▾] [Country ▾] [Segment ▾]                  [Clear filters]  │
├────────────┬────────────┬────────────┬────────────┬───────────────────────────┤
│ Total      │ Orders     │ Customers  │ AOV        │ Revenue growth            │
│ Revenue    │            │            │            │ (latest complete month)   │
├────────────┴────────────┴────────────┴────────────┴───────────────────────────┤
│ Revenue trend (monthly line; complete vs partial)                              │
├───────────────────────────────────────┬───────────────────────────────────────┤
│ Revenue by category (top 10 bars)     │ Customer segments (donut)             │
└───────────────────────────────────────┴───────────────────────────────────────┘
```

| ID | Visual | Fields | Notes |
|---|---|---|---|
| 1.1 | Card | `[Total Revenue]` | Currency; subtitle "Total revenue" |
| 1.2 | Card | `[Total Orders]` | Unavailable without `TRANSACTION_ID` |
| 1.3 | Card | `[Total Customers]` | Unavailable without `CUSTOMER_ID` |
| 1.4 | Card | `[Average Order Value]` | |
| 1.5 | Card (KPI) | `[Revenue Growth]` | Conditional color: positive `#3FB68B`, negative `#E5645A`; blank shows "—" and tooltip "Fewer than two consecutive complete months." |
| 1.6 | Line chart | X: `dim_date[month_short]` sorted by month (axis: `year_month`); Y: `[Revenue (Complete Months)]` solid + `[Revenue (Partial Months)]` dashed, color `#8A94A6` | Legend labels: "Complete month", "Partial month"; title "Monthly revenue (₹)" with units from currency |
| 1.7 | Clustered bar | Y: `dim_product[category]` (top 10 by `[Total Revenue]`, filter `is_unknown`/`category <> "Unknown"`); X: `[Total Revenue]` | Data labels on; sorted descending |
| 1.8 | Donut | Legend: `dim_customer[segment]`; Values: `[Total Customers]` | Fixed segment colors (§8.7); title "Customers by segment (as of {reference_date})"; unavailable without RFM |

## 8.4 Page 2 — Customer Analytics

| ID | Visual | Fields | Notes |
|---|---|---|---|
| 2.1 | Card | `[Total Customers]` | |
| 2.2 | Card | `[Repeat Customer Rate]` | |
| 2.3 | Card | `[Revenue per Customer]` | |
| 2.4 | Card | `[Orders per Customer]` | |
| 2.5 | Bar | Y: `dim_customer[segment]`; X: `[Segment Customer Share]` and `[Segment Revenue Share]` (clustered, two series) | Shows concentration (revenue share vs customer share); fixed segment order by `segment_sort` |
| 2.6 | Matrix (heatmap) | Rows: `dim_customer[r_score]` (5→1); Columns: `dim_customer[f_score]` (1→5); Values: `[Total Customers]`; conditional formatting: sequential amber scale (DESIGN §2.4) | "RFM: recency × frequency (as of {reference_date})" |
| 2.7 | Stacked column | X: `dim_date[year_month]`; Y: `[New Customers]`, `[Returning Customers]` | Complete months only (visual filter); footnote: first data month excluded/annotated |
| 2.8 | Table | Columns: `dim_customer[customer_id]` (per PII mode), `[Total Revenue]`, `[Total Orders]`, `dim_customer[rfm_score]`, `dim_customer[segment]` | Top 20 by `[Total Revenue]`; hidden if PII mode is `OMIT` (replaced by `customer_key`-free aggregate: segment table only) |

Unavailable (reason shown on page): *"RFM Segments, Repeat Purchase Rate and Customer Revenue need a customer identifier."* — page omitted when `dim_customer` is absent.

## 8.5 Page 3 — Product Analytics

| ID | Visual | Fields | Notes |
|---|---|---|---|
| 3.1 | Clustered bar | Y: `dim_product[product_name]` (Top 10 by `[Total Revenue]`, exclude `is_unknown`); X: `[Total Revenue]` | "Top 10 products" |
| 3.2 | Clustered bar | Y: `dim_product[product_name]` (**Bottom** 10 by `[Total Revenue]`, exclude `is_unknown`); X: `[Total Revenue]` | "Bottom 10 products" (products with ≥ 1 sale) |
| 3.3 | Column or treemap | Category: `dim_product[category]`; Values: `[Total Revenue]` | "Revenue by category" |
| 3.4 | Column | Category: `dim_product[category]`; Values: `[Total Quantity]` | Unavailable without `QUANTITY` |
| 3.5 | Table | `dim_product[product_name]`, `dim_product[category]`, `[Total Revenue]`, `[Product Revenue Share]`, `[Total Quantity]` | Sortable; top 50 |
| 3.6 | Card | Share of revenue from top-10 products: `DIVIDE ( CALCULATE ( [Total Revenue], TOPN ( 10, ALL ( dim_product[product_natural_key] ), [Total Revenue] ) ), CALCULATE ( [Total Revenue], ALL ( dim_product ), dim_product[is_unknown] = FALSE () ) )` | Measure name **Top 10 Product Share**; contextual; tie order may differ from SQL's key tie-break, so it is **excluded from parity** |

Category/product visuals use product-level and category-level semantics consistent with SQL_SPEC §10.3–10.4.

## 8.6 Page 4 — Purchase Behavior and Page 5 — Geography

### Page 4 — Purchase Behavior

| ID | Visual | Fields | Notes |
|---|---|---|---|
| 4.1 | Combo (column + line) | X: `dim_discount_band[discount_band]`; Columns: `[Total Revenue]`; Line: `[Total Orders]` | Title "Revenue and orders by discount band"; association caption |
| 4.2 | Line | X: `dim_discount_band[discount_band]`; Y: `[Average Order Value]` | Caveat tooltip: "Orders can span discount bands; band AOV = band revenue ÷ orders touching the band." |
| 4.3 | Donut | Legend: `dim_payment[payment_method]`; Values: `[Total Revenue]` | ≤ 5 slices, otherwise horizontal bars (visual switched at generation time using member count ≤ 5) |
| 4.4 | Clustered bar | Y: `dim_payment[payment_method]`; X: `[Average Order Value]` | |
| 4.5 | Column | X: `fact_sales[order_size_bucket]` (sorted by `order_size_sort`); Y: `[Total Orders]` | "Orders by number of lines" |
| 4.6 | Column | X: `dim_customer[purchase_frequency_bucket]`; Y: `[Total Customers]` | "Customers by number of orders (as of {reference_date})" |
| 4.7 | Card | `[Average Basket Quantity]` | |
| 4.8 | Card | `[Average Lines per Order]` | |

Margin visuals are **not** generated (no cost data in V1; SQL_SPEC §5.8) and are listed as unavailable with the reason.

### Page 5 — Geography

| ID | Visual | Fields | Notes |
|---|---|---|---|
| 5.1 | Matrix | Rows: Location hierarchy (country → state → city); Values: `[Total Revenue]`, `[Total Customers]`, `[Total Orders]` | Expand/collapse enabled |
| 5.2 | Clustered bar | Y: `dim_location[country]`; X: `[Total Revenue]` (top 10) | If `country` unmapped, uses the most specific mapped level |
| 5.3 | Clustered bar | Y: `dim_location[state]`; X: `[Total Revenue]` (top 10) | Requires `STATE` |
| 5.4 | Clustered bar | Y: `dim_location[city]`; X: `[Total Revenue]` (top 10) | Requires `CITY` |
| 5.5 | Bar | Y: location level; X: `[Total Customers]` | Customer distribution |
| 5.6 | Card | Revenue share of the top region: `[Country Revenue Share]` for the leading country (visual-level TopN 1) | Optional |
| 5.7 | Filled map (**optional**) | Location: `dim_location[country]`; Size: `[Total Revenue]` | Requires Bing/Azure map geocoding to be enabled in the tenant/Desktop; generated only if `powerbi_include_maps = true`; otherwise omitted with note |

## 8.7 Theme (`theme/insightforge-dark.json`)

Colors from `DESIGN.md` §2:

```json
{
  "name": "InsightForge Dark",
  "dataColors": ["#E8A33D", "#5B9BD5", "#3FB68B", "#B58AE0", "#E5645A", "#4FC1C7", "#C9C14A", "#8A94A6"],
  "background": "#0B0D10",
  "secondaryBackground": "#14181D",
  "foreground": "#E8EBEF",
  "tableAccent": "#E8A33D",
  "firstLevelElements": "#E8EBEF",
  "secondLevelElements": "#A3ACB9",
  "thirdLevelElements": "#2A313B",
  "fourthLevelElements": "#6E7887",
  "good": "#3FB68B",
  "neutral": "#E0B341",
  "bad": "#E5645A",
  "maximum": "#E8A33D",
  "center": "#1A1F26",
  "minimum": "#5B9BD5",
  "null": "#4A525E",
  "textClasses": {
    "callout": { "fontSize": 28, "fontFace": "Segoe UI Semibold", "color": "#E8EBEF" },
    "title":   { "fontSize": 14, "fontFace": "Segoe UI Semibold", "color": "#E8EBEF" },
    "header":  { "fontSize": 12, "fontFace": "Segoe UI Semibold", "color": "#A3ACB9" },
    "label":   { "fontSize": 11, "fontFace": "Segoe UI",          "color": "#A3ACB9" }
  },
  "visualStyles": {
    "*": {
      "*": {
        "background":   [{ "color": { "solid": { "color": "#14181D" } }, "transparency": 0 }],
        "border":       [{ "show": true, "color": { "solid": { "color": "#2A313B" } }, "radius": 8 }],
        "title":        [{ "show": true, "fontColor": { "solid": { "color": "#E8EBEF" } }, "fontSize": 14 }],
        "visualHeader": [{ "show": false }]
      }
    }
  }
}
```

**Fixed segment colors (DESIGN §2.4):** High Value `#E8A33D`, Regular `#5B9BD5`, Occasional `#4FC1C7`, At Risk `#E5645A` — applied via per-data-point formatting documented in the dashboard spec (so segments look the same in the web app, report, deck, and Power BI).

Accessibility: text/background contrast meets WCAG AA (`#E8EBEF` on `#14181D` ≈ 14:1; `#A3ACB9` ≥ 7:1). `#6E7887` (4th level) is used for non-essential gridlines/hints only. Color is never the only encoding (labels, markers, ordering).

## 8.8 `dashboard_spec.json` shape

```json
{
  "canvas": { "width": 1280, "height": 720, "theme": "theme/insightforge-dark.json" },
  "slicers": [
    { "id": "S1", "field": "dim_date[date]", "type": "BETWEEN", "synced_pages": [1,2,3,4,5] }
  ],
  "pages": [
    {
      "number": 1, "title": "Executive Overview", "available": true,
      "visuals": [
        { "id": "1.1", "type": "CARD", "title": "Total revenue", "measures": ["Total Revenue"],
          "available": true, "alt_text": "Total revenue across the selected period",
          "position": { "x": 48, "y": 96, "w": 232, "h": 96 } },
        { "id": "1.3", "type": "CARD", "title": "Customers", "measures": ["Total Customers"],
          "available": false, "reason": "A customer identifier is required.", "missing_roles": ["CUSTOMER_ID"] }
      ]
    },
    { "number": 5, "title": "Geography", "available": false,
      "reason": "No country, state or city column was detected.", "missing_roles": ["COUNTRY","STATE","CITY"] }
  ]
}
```
Visual `type` ∈ `CARD, LINE, COLUMN, BAR, CLUSTERED_BAR, COMBO, DONUT, MATRIX, TABLE, TREEMAP, MAP`. Positions are given for generated visuals; the Markdown spec renders the same data as wireframes and tables.

---

# 9. Parity and Verification Strategy

## 9.1 `verification/reference_values.json`

Generated from persisted **metrics** (not recomputed):

```json
{
  "scope": "UNFILTERED",
  "currency": "INR",
  "values": [
    { "measure": "Total Revenue", "metric_name": "total_revenue", "metric_id": "…",
      "expected": "8420312.4839200000", "unit": "currency", "tolerance": { "abs": 0.005, "rel": 1e-9 } },
    { "measure": "Repeat Customer Rate", "metric_name": "repeat_purchase_rate", "metric_id": "…",
      "expected": "0.3412000000", "unit": "ratio", "tolerance": { "abs": 1e-9 } },
    { "measure": "Segment Revenue Share", "dimensions": { "segment": "High Value" },
      "metric_name": "segment_revenue_share", "metric_id": "…", "expected": "0.5170000000", "unit": "ratio", "tolerance": { "abs": 1e-9 } }
  ],
  "row_counts": { "fact_sales": 125106, "dim_customer": 17333 }
}
```

## 9.2 Verification levels

| Level | What | Where | Gate |
|---|---|---|---|
| **L0 — Static** | DAX lint: balanced syntax, function allow-list, every referenced table/column exists in `schema.json`, no hard-coded numbers, no unavailable measure emitted; M query lint | CI (Linux) | Blocks merge |
| **L1 — Semantic reference evaluation** | A **Python reference evaluator** implements each parity measure's *semantics* over the exported package tables (Polars) and compares to persisted metrics and `reference_values.json` within tolerance. This verifies the **data contract** (keys, flags, snapshots, Unknown members) and the **measure logic**, not the DAX engine itself | CI (Linux) | Blocks merge |
| **L2 — DAX engine execution** | Load the package into a local Tabular engine (Power BI Desktop's Analysis Services instance or an equivalent) via XMLA and execute `EVALUATE ROW(...)` for every parity measure under an empty filter context; compare to `reference_values.json` | Nightly / pre-release on a **Windows runner**; also available to users as a manual checklist (§11) | Blocks release; failures open a defect |
| **L3 — Manual user check** | README checklist: the user compares card values to `reference_values.json` and the app's evidence drawer | End user | Informational |

> **Honest scope:** L0/L1 run in standard CI. L2 requires a Windows environment with Power BI Desktop/Analysis Services and is therefore a scheduled job, not a per-commit gate (ADR-022 tracks infrastructure).

## 9.3 Tolerances

| Value type | Tolerance (under empty filter context) |
|---|---|
| Counts (customers, orders) | **Exact** |
| Currency/quantity (Fixed decimal columns) | **Exact** after rounding to the column's scale |
| Currency/quantity (double columns) | `abs ≤ 0.005` **or** `rel ≤ 1e-9` (whichever is larger) |
| Ratios and growth | `abs ≤ 1e-9` |
| Averages | `rel ≤ 1e-9` |

Reference values are strings (exact decimals); evaluators compare using `Decimal` and tolerances above.

## 9.4 Reconciliation checks in the builder (hard failures)

1. `COUNT(fact_sales) = dataset_versions.row_count`
2. `SUM(fact_sales.revenue) = total_revenue` (within §9.3)
3. Every non-blank, non-`-1` foreign key in the fact exists in its dimension; dimension keys are unique
4. `SUM(customer_segments counts) = total_customers` (when RFM available)
5. `SUM(revenue by category incl. Unknown) = total_revenue`
6. `dim_date` is contiguous with unique dates; every fact `date_key` exists in it
7. No NaN/Infinity in numeric columns; no scientific notation in CSV

---

# 10. Generation Lifecycle, API, and Persistence

## 10.1 Flow

```text
POST /analysis-runs/{id}/powerbi  (Idempotency-Key)   → 202, powerbi_models.status = QUEUED
   └─ generate queue worker → GENERATING → (steps §6.2) → READY | FAILED
GET  /analysis-runs/{id}/powerbi                      → status + schema + measures + dashboard_spec + package info
POST /powerbi-models/{id}/download-url                → presigned URL (5 min); audit powerbi.downloaded
```

Preconditions (API_SPEC §7.14): run `COMPLETED` (`RUN_NOT_COMPLETED`) and a buildable fact (`MODULE_UNAVAILABLE` otherwise). The generation may also be requested automatically via the run's `generate.powerbi = true` option.

## 10.2 Idempotency (PBI-P-03)

- One `powerbi_models` row per run (`run_id` unique, `DATABASE.md` §6.9).
- Re-requesting with identical inputs and `model_version` returns the existing model (`200`, `Idempotent-Replay: true`). A newer `model_version` (after a platform upgrade) allows **regeneration** that replaces the package and updates `model_version`, `generated_at`, and checksums; the previous object is deleted after the new one is committed.
- Inputs are pinned by the run (`dataset_version_id`, `config_hash`, `mapping_hash`, `pipeline_version`); changing the mapping requires a **new run**.

## 10.3 Database mapping (`powerbi_models`)

| Column | Content |
|---|---|
| `status` | `QUEUED, GENERATING, READY, FAILED, EXPIRED` |
| `schema_def` | `schema.json` (tables, columns with Power BI types, keys, relationships, hierarchies, unavailable list) |
| `measures` | `measures.json` array |
| `dashboard_spec` | `dashboard_spec.json` |
| `storage_key` / `size_bytes` / `checksum_sha256` | The ZIP package |
| `model_version` | `1` |
| `generated_at` / `expires_at` | Retention per `GENERATED_FILE` policy (default 90 days); expired packages are regenerable from the run |

`schema.json` example:
```json
{
  "fact": "fact_sales",
  "dimensions": ["dim_customer", "dim_product", "dim_date", "dim_location", "dim_payment", "dim_discount_band"],
  "tables": [
    {
      "name": "fact_sales", "grain": "one row per cleaned source row", "rows": 125106,
      "columns": [
        { "name": "revenue", "power_bi_type": "FIXED_DECIMAL", "role": "MEASURE_SOURCE", "hidden": false, "derived": false },
        { "name": "customer_key", "power_bi_type": "WHOLE_NUMBER", "role": "FOREIGN_KEY", "hidden": true, "references": "dim_customer.customer_key" }
      ]
    }
  ],
  "relationships": [
    { "from": "fact_sales.customer_key", "to": "dim_customer.customer_key", "cardinality": "MANY_TO_ONE", "cross_filter": "SINGLE" }
  ],
  "hierarchies": [ { "table": "dim_date", "name": "Date Hierarchy", "levels": ["year", "quarter_label", "month_name", "date"] } ],
  "unavailable": []
}
```
This matches the response shape in `API_SPEC.md` §7.14 (`schema.fact`, `schema.dimensions`, `schema.tables`, `schema.relationships`).

## 10.4 Events, notifications, audit

- SSE `artifact.ready` (`type: POWERBI_MODEL`) and an in-app notification `EXPORT_COMPLETED`-class message on success; `PROCESSING_FAILED` on failure.
- Audit: `powerbi.generated`, `powerbi.downloaded` (`DATABASE.md` §6.10).

## 10.5 Failure modes

| Condition | Behavior |
|---|---|
| Run not completed | `409 RUN_NOT_COMPLETED` |
| No buildable fact (no revenue) | `409 MODULE_UNAVAILABLE` with reason |
| Too many fact rows (`POWERBI_MAX_FACT_ROWS`, default 5,000,000) | Model `FAILED`, `error_code = POWERBI_MODEL_TOO_LARGE`, remedy "Filter or aggregate the dataset, or raise the limit." |
| Reconciliation failure (§9.4) | `FAILED`, `error_code = POWERBI_RECONCILIATION_FAILED` (internal; diagnostic reference, no details leaked) |
| Storage/transient errors | Auto-retry per job policy (`ARCHITECTURE.md` §9.4) |
| Package expired | `410 ARTIFACT_EXPIRED` on download; regenerate |

---

# 11. Import Instructions (`README.md` content)

**Requirements:** Power BI Desktop (current release), Windows. Set the Desktop locale to match your region (e.g., `en-IN`) for number grouping.

1. **Unzip** the package to a folder, e.g. `C:\InsightForge\retail-sales-analysis`.
2. **Open Power BI Desktop → Transform data → Manage Parameters → New**: name `DataFolder`, type Text, value = the `data` folder path (e.g., `C:\InsightForge\retail-sales-analysis\data`).
3. **Create queries:** for each file in `model/queries/` (`fact_sales.pq`, `dim_*.pq`), choose *New Source → Blank Query → Advanced Editor* and paste the contents; name the query exactly as the file (e.g., `fact_sales`). **Close & Apply.**
4. **Relationships:** *Model view → Manage relationships* — create the relationships listed in `model/relationships.json` (many-to-one, single direction, dimension filters fact).
5. **Date table:** select `dim_date` → *Mark as date table* → column `date`.
6. **Metadata:** hide key/flag/helper columns, set *Sort by column* and *Data category* as listed in `model/schema.md` (§"Column metadata").
7. **Measures:** create a **blank table named `_Measures`** (Enter data) and add each measure from `model/measures.dax`, or paste into *Tabular Editor/DAX Studio*; set display folders and formats from `measures.json`.
8. **Theme:** *View → Themes → Browse for themes →* `theme/insightforge-dark.json`.
9. **Build pages:** follow `spec/dashboard_spec.md` page by page (visual type, fields, filters, titles, alt text).
10. **Verify (L3):** compare these cards (no slicers applied) with `verification/reference_values.json`:

```text
Total Revenue ........ expected ₹8,420,312.48
Total Orders ......... expected 62,411
Total Customers ...... expected 17,333
Average Order Value .. expected ₹134.92
Repeat Customer Rate . expected 34.1%
```
(These numbers are generated per package; the example values are illustrative.)

> **Why not a single click?** V1 generates a model *specification* and data (PRD §55, §9.4). A one-step PBIP/TMDL import is planned (ADR-020).

---

# 12. Security and Privacy

| Concern | Control |
|---|---|
| Ownership | Generation, status, and downloads are owner-scoped (`404` for foreign resources); presigned URLs issued only after authorization, TTL 5 minutes, never listed in payloads |
| PII | `dataset_columns.is_pii_suspected` drives `powerbi_pii_mode`: **`INCLUDE`** (default; raw identifiers) · **`HASH`** (`sha256:` + first 16 hex of `HMAC-SHA256(secret_per_package, value)`; the secret is **not** included; hashes are consistent within the package only) · **`OMIT`** (identifier column omitted; `dim_customer` keyed only by `customer_key`; customer-level tables removed from page 2). The mode and affected columns are listed in the manifest and README |
| Data minimization | No raw columns outside the mapped roles are exported; unmapped/unknown columns are **not** included in the package |
| File safety | No macros/scripts in the package; M queries are plain `.pq` text; text cells are sanitized for spreadsheet formula injection (§6.4); package built from trusted generators only |
| Secrets | No credentials, tokens, or URLs in the package; `DataFolder` is a local path parameter |
| Integrity | `manifest.json` includes SHA-256 for every file; the package checksum is stored in `powerbi_models.checksum_sha256` |
| Retention | Per `GENERATED_FILE` policy; deleted with the project purge (`DATABASE.md` §12.3) |
| Audit | `powerbi.generated|downloaded` events; no data values in audit metadata |

Users are informed in the README that the package contains their dataset in plain files and should be stored accordingly.

---

# 13. Performance and Limits

| Concern | Rule |
|---|---|
| Fact size | Default cap 5,000,000 rows (`POWERBI_MAX_FACT_ROWS`); typical retail datasets (≤ 1M rows) load in seconds–minutes in Desktop |
| Package size | Compressed ZIP; CSV preferred for compatibility; optional Parquet reduces size and speeds import |
| Generation time | Streamed build via Polars/Arrow; memory-bounded per worker (`ARCHITECTURE.md` §10.7); progress via job events |
| Model design | Single fact + narrow dimensions; integer keys; hidden helper columns; no calculated columns in the model; measures only (V1) |
| Cardinality | `dim_customer` can be large (one row per customer); high-cardinality text (e.g., `customer_id`) is the only wide text column; `OMIT`/`HASH` reduce size and risk |
| Dashboard | ≤ 8 visuals/page; Top-N visual filters; no visual-level DAX over iterators of fact rows except documented measures |

---

# 14. Testing Requirements (PRD §80–81)

| Test | Verifies | Req |
|---|---|---|
| **Builder unit tests** | Key assignment (dense rank, binary collation), Unknown members, flags, order attributes, bucket boundaries, snapshot columns | PBI-M-04/05 |
| **Golden dataset tests** | Using the PRD §81 fixture (Customer A ₹100 + ₹200, Customer B ₹300): `Total Revenue = 600`, customers = 2, revenue A = B = 300 in the package and via L1 evaluator | PBI-D-02 |
| **Reconciliation tests** | §9.4 checks pass for golden/fuzzed datasets; each check has a failing-input test | PBI-M-07 |
| **Referential integrity tests** | No orphan keys except documented blanks; dimension keys unique | PBI-M-04 |
| **Parity tests (L1)** | Every parity measure equals its metric within §9.3 for: complete data; missing `TRANSACTION_ID`; missing `CUSTOMER_ID`; derived revenue; partial first/last months; gap months; single complete month; zero-revenue months; ties; NULL categories/products/locations/payments | PBI-D-02/05 |
| **DAX/M lint (L0)** | Syntax, allow-listed functions, existing references, no hard-coded values, availability gating | PBI-D-03/04 |
| **Engine execution (L2)** | All parity measures evaluate in a Tabular engine under empty context and match reference values | PBI-D-02 |
| **Determinism tests** | Same inputs ⇒ identical file hashes (manifest `generated_at` excluded); ZIP byte-identical | PBI-P-03 |
| **Availability tests** | Datasets lacking roles omit the right tables/measures/pages and record reasons; `MODULE_UNAVAILABLE` when no fact is buildable | PBI-M-03, PBI-B-02 |
| **PII mode tests** | `INCLUDE/HASH/OMIT` outputs; hashes stable within package; omitted columns absent everywhere (tables, M queries, spec) | PBI-M-10 |
| **CSV/M type tests** | Round-trip: engine → CSV → Polars with the M type map equals source values; locale-independent parsing (`en-US` culture in M) | PBI-M-08 |
| **Theme/accessibility tests** | Contrast ratios computed from theme JSON meet AA; palette equals `DESIGN.md` tokens | PBI-B-05 |
| **Spec consistency tests** | Every measure referenced by a visual exists and is available; every visual field exists in `schema.json`; page/visual availability matches measure/table availability | PBI-B-01/02 |
| **Report-consistency test** | Numbers in reports/decks and `reference_values.json` resolve to the same persisted metrics | P9 |
| **API/flow tests** | Idempotent POST, status transitions, presigned download TTL, expiry → `410`, authorization matrix (user B → `404`) | PBI-P-01/04 |
| **Load/size tests** | 1M and 5M row packages generate within memory limits; over-limit fails with `POWERBI_MODEL_TOO_LARGE` | §13 |

---

# 15. Versioning and Change Control

| Item | Rule |
|---|---|
| `model_version` | Integer in `powerbi_models.model_version` and `manifest.json`; increments on **any** change to table/column definitions, key rules, measure DAX, dashboard spec, or theme that affects users |
| `PIPELINE_VERSION` | Bumped when SQL relations/templates/metric bindings change (`SQL_SPEC.md` §16); the Power BI model must be re-validated and `model_version` bumped if derived relations change |
| Backward compatibility | Old packages remain valid artifacts; a new `model_version` is applied only on regeneration |
| Deprecation | Retired measures remain in `measures.json` history for old runs; names are not reused with different semantics |
| Review checklist | DAX change ⇒ L0 + L1 + L2 results, updated parity table, README/spec updates, `DECISIONS.md` entry if a modeling decision changes |

---

# 16. Open Items and Decisions (`DECISIONS.md`)

| ID | Item | Status / Impact |
|---|---|---|
| ADR-020 | Generate **PBIP/TMDL** or a **Tabular Editor script** to remove manual model assembly | Proposed (P2); formats here are designed to support it |
| ADR-021 | Add `dim_discount_band` (and `order_size_bucket` helper) to the PRD §55 star schema | Proposed; documents an extension needed by PRD §42/§57 |
| ADR-022 | CI infrastructure for L2 DAX execution (Windows runner + Analysis Services/Power BI Desktop) | Proposed |
| ADR-023 | CSV (default) vs Parquet (default) packaging | Current: CSV default, Parquet optional |
| **Conflict to resolve (PRD §127)** | `SQL_SPEC.md` `pay_summary` and `disc_band_summary` compute AOV as `SUM(revenue) / COUNT(DISTINCT transaction_id)` over **all** rows with a non-null payment/discount, whereas the global AOV (`orders`) excludes rows with `NULL transaction_id` from the numerator. The Power BI `Average Order Value` measure follows the global definition. The two agree when no row lacks a `transaction_id` and differ otherwise | **Recommendation:** update `SQL_SPEC.md` §10.7/§10.8 to add `transaction_id IS NOT NULL` to those templates (and bump `PIPELINE_VERSION`) so every AOV in the platform shares one definition; until then, parity fixtures for these slices must contain no `NULL` `transaction_id` |
| API catalog | New payload `error_code`s: `POWERBI_MODEL_TOO_LARGE`, `POWERBI_RECONCILIATION_FAILED` | Add to `API_SPEC.md` §4.3 "Artifacts & AI" (payload codes) |
| Project settings | `powerbi_pii_mode`, `powerbi_include_parquet`, `powerbi_include_maps`, `POWERBI_MAX_FACT_ROWS` | Add to `projects.settings` contract (`DATABASE.md` §7) and `GET /meta/config` limits |
| Locale/format | Indian digit grouping (₹84.20L) cannot be encoded in DAX format strings | Documented as locale guidance; revisit if a custom format approach is adopted |
| Margin | No cost role in V1 | Requires PRD §23 update before margin visuals/measures can exist |
| Spearman/correlation in DAX | Not provided; platform metric only | Revisit if native DAX support is desired |
| Snapshot attributes on `dim_customer` | Not slicer-responsive by design | Alternative: separate RFM snapshot table with explicit "as of" labeling |

---

# 17. Traceability to PRD

| PRD Section | POWERBI_SPEC Section |
|---|---|
| §9.4 No Power BI cloud automation in V1 | §1.3, §4.3 |
| §55 Power BI integration (star schema) | §3.1, §5 |
| §56 Power BI measures | §3.2, §7.2–7.4 |
| §57 Power BI dashboard (5 pages) | §3.3, §8 |
| §60, §96 Single source of truth | §2 (P1, P2, P9), §6.1, §9 |
| §42 Discount: association vs causation | §2 (P6), §7.3, §8.2, §8.6 |
| §65–66, §116 Partial analysis / availability | §2 (P4), §5.2, §8.1, §10.5 |
| §63 Background processing | §3.4, §10.1 |
| §67, §82 Privacy & security | §12 |
| §68 File storage | §4.1, §10.3 |
| §79 Auditability | §10.4, §12 |
| §80–81 Testing, analytics correctness | §9, §14 |
| §95 Reproducibility | §4.2, §6.3, §10.2 |
| §98 Design requirements (visual identity) | §8, §8.7 |
| §107 Export | §4, §10 |
| §112–114 Currency, dates, precision | §6.6, §7.1, §9.3 |
| §126 Prohibited shortcuts (no fake results) | §2, §3.2 (PBI-D-03/04), §9 |
