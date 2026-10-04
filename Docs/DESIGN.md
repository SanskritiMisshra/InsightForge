# InsightForge — Design Specification (DESIGN.md)

**Version:** 1.0
**Status:** Authoritative for all frontend work
**Depends on:** `PRD.md` (§70–74, §91, §98–99)
**Stack:** Next.js · TypeScript · Tailwind CSS · Reusable component system

> If this document conflicts with `PRD.md`, the conflict must be identified and resolved before implementation continues (PRD §127).

---

# 1. Design Philosophy

## 1.1 One-sentence direction

> InsightForge looks like a precision instrument: dark, quiet, dense, and exact — where the data is the brightest thing on screen.

## 1.2 Core principles

1. **Data is the hero.** Chrome (sidebar, headers, borders) recedes. Numbers, charts, and tables carry the contrast.
2. **Density with hierarchy.** High information density is a requirement (PRD §98), but every screen has exactly one primary focal point and a clear reading order.
3. **Evidence is one click away.** Any number that appears as an insight, KPI, or report figure must offer a path to its source: metric → SQL → calculation (PRD §50, §131).
4. **Honest visuals.** Axes start where they should, scales are labeled, missing data is shown as missing, and association is never styled as causation (PRD §34, §91).
5. **Calm by default, loud only for problems.** Color is semantic. The accent is used sparingly; red/amber appear only when something needs attention.
6. **State-complete.** No screen ships without Loading, Skeleton, Empty, Success, Error, Processing, Partial, and Retry states (PRD §72).
7. **Consistency over novelty.** A new screen is assembled from existing components. A new component is created only when no existing one fits.

## 1.3 What InsightForge must NOT look like (PRD §98)

| Avoid | Why |
|---|---|
| Purple/blue "AI" gradients, gradient text, gradient buttons | Generic AI-dashboard cliché |
| Neon glows, outer-glow shadows | Reads as gaming UI, not analytics |
| Heavy glassmorphism / blurred translucent panels | Hurts legibility and density |
| Giant hero typography inside the app | Wastes space; app is a tool, not a landing page |
| Decorative animation, parallax, floating blobs | Distracts from data |
| Random chart colors | Color must encode meaning |
| Emoji as iconography | Use the icon system |
| Rounded "bubbly" cards with big padding | Contradicts density |
| Fake/lorem numbers in production screens | PRD §126 |

## 1.4 Mood references (qualitative)

Think: a trading terminal's discipline, a modern developer-tool's polish, and a financial report's clarity. Restrained, technical, premium.

---

# 2. Design Tokens

All tokens are defined once as CSS variables and surfaced through the Tailwind theme. **No raw hex values are permitted in components.**

## 2.1 Color — Neutrals (dark theme, primary)

A cool-neutral scale with a very slight blue-gray tint to feel technical without looking blue.

| Token | Hex | Usage |
|---|---|---|
| `--bg-base` | `#0B0D10` | App background |
| `--bg-subtle` | `#0F1216` | Sidebar, page sections |
| `--bg-surface` | `#14181D` | Cards, panels, table body |
| `--bg-raised` | `#1A1F26` | Popovers, dropdowns, hovered rows |
| `--bg-overlay` | `#212731` | Modals, command palette |
| `--border-subtle` | `#1F252D` | Dividers inside cards, table rows |
| `--border-default` | `#2A313B` | Card borders, inputs |
| `--border-strong` | `#3A424F` | Hover/focus-adjacent borders |
| `--text-primary` | `#E8EBEF` | Headings, key numbers |
| `--text-secondary` | `#A3ACB9` | Body, labels |
| `--text-tertiary` | `#6E7887` | Hints, captions, axis labels |
| `--text-disabled` | `#4A525E` | Disabled text |

## 2.2 Color — Accent ("Ember")

The brand accent evokes a forge — a muted amber. It is the **only** brand color and is used for primary actions, active navigation, focus rings, and the single highlighted series in a chart.

| Token | Hex | Usage |
|---|---|---|
| `--accent-500` | `#E8A33D` | Primary buttons, active indicator, key highlights |
| `--accent-400` | `#EDB45E` | Hover |
| `--accent-600` | `#C98724` | Pressed |
| `--accent-subtle` | `rgba(232,163,61,0.12)` | Active nav background, selected row tint |
| `--accent-border` | `rgba(232,163,61,0.35)` | Selected card border, focus ring |
| `--on-accent` | `#15100A` | Text on accent backgrounds |

> Accent usage budget: at most **one primary accent action per view region** and no more than ~5% of visible pixels.

## 2.3 Color — Semantic

| Role | Foreground | Background tint | Border |
|---|---|---|---|
| Success | `#3FB68B` | `rgba(63,182,139,0.12)` | `rgba(63,182,139,0.35)` |
| Warning | `#E0B341` | `rgba(224,179,65,0.12)` | `rgba(224,179,65,0.35)` |
| Danger | `#E5645A` | `rgba(229,100,90,0.12)` | `rgba(229,100,90,0.35)` |
| Info | `#5B9BD5` | `rgba(91,155,213,0.12)` | `rgba(91,155,213,0.35)` |
| Neutral | `#A3ACB9` | `rgba(163,172,185,0.10)` | `rgba(163,172,185,0.25)` |

Warning (`#E0B341`) is deliberately distinct from the accent (`#E8A33D`) by usage context: warning always appears with an icon and label inside a badge/banner; the accent never appears as a standalone text color for status.

## 2.4 Color — Data Visualization

### Categorical palette (8 series, color-blind-safe ordering)

| # | Token | Hex |
|---|---|---|
| 1 | `--viz-1` | `#E8A33D` (accent amber) |
| 2 | `--viz-2` | `#5B9BD5` (steel blue) |
| 3 | `--viz-3` | `#3FB68B` (green) |
| 4 | `--viz-4` | `#B58AE0` (soft violet) |
| 5 | `--viz-5` | `#E5645A` (coral) |
| 6 | `--viz-6` | `#4FC1C7` (teal) |
| 7 | `--viz-7` | `#C9C14A` (olive-yellow) |
| 8 | `--viz-8` | `#8A94A6` (slate gray) |

Rules:
- Single-series charts use `--viz-1`.
- Comparisons use `--viz-1` for the focus series and `--viz-8` (gray) for context series.
- Never exceed 8 categorical colors; group the remainder into "Other" using `--viz-8`.
- Series identity must not rely on color alone: use direct labels, legends with markers, or pattern/dash differences for line charts.

### Sequential scale (heatmaps, density)

`#1A1F26 → #3A3320 → #6B4F1E → #B07A22 → #E8A33D → #F5D08F` (low → high, single-hue amber).

### Diverging scale (correlation matrix, growth)

`#5B9BD5 (−1) → #1A1F26 (0) → #E8A33D (+1)`. Always show the legend with 0 labeled.

### Segment colors (customer segments — fixed mapping, PRD §39)

| Segment | Color |
|---|---|
| High Value | `--viz-1` |
| Regular | `--viz-2` |
| Occasional | `--viz-6` |
| At Risk | `--viz-5` |

Segment colors are fixed across every screen (Customers, Insights, Power BI spec, reports).

## 2.5 Light theme

V1 ships **dark theme only** as the primary experience. The token architecture must support a light theme later; therefore components must reference tokens only. A light theme is not a V1 deliverable.

## 2.6 Typography

| Role | Family | Fallback |
|---|---|---|
| UI / body | **Inter** (variable) | `ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif` |
| Numbers, code, SQL, IDs | **JetBrains Mono** | `ui-monospace, "SF Mono", Menlo, Consolas, monospace` |

Loaded via `next/font` (self-hosted, `display: swap`). Enable Inter's tabular numbers (`font-feature-settings: "tnum" 1, "cv11" 1`) on **all numeric displays** so columns align.

### Type scale

| Token | Size / Line | Weight | Tracking | Usage |
|---|---|---|---|---|
| `text-display` | 28 / 34 | 600 | −0.02em | Landing hero only |
| `text-h1` | 22 / 28 | 600 | −0.01em | Page title |
| `text-h2` | 17 / 24 | 600 | −0.005em | Section title |
| `text-h3` | 14 / 20 | 600 | 0 | Card title |
| `text-body` | 13 / 20 | 400 | 0 | Default text |
| `text-body-lg` | 14 / 22 | 400 | 0 | Descriptions, insight body |
| `text-caption` | 12 / 16 | 400 | 0 | Hints, axis labels |
| `text-overline` | 11 / 14 | 500 | +0.06em, uppercase | Section labels, table headers |
| `text-kpi` | 28 / 32 | 600 | −0.02em | KPI values (mono-tabular) |
| `text-kpi-sm` | 20 / 24 | 600 | −0.01em | Secondary KPI values |
| `text-code` | 12.5 / 20 | 400 | 0 | SQL, mono data |

Rules:
- Default UI text is **13px**. This is intentional for density.
- Never exceed `text-h1` inside the authenticated app (except KPI values).
- Max line length for prose (insights, descriptions): **72ch**.
- Text color defaults: headings `--text-primary`, body `--text-secondary`, captions `--text-tertiary`.

## 2.7 Spacing

Base unit **4px**. Allowed scale: `0, 2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64`.

| Context | Value |
|---|---|
| Inline icon–label gap | 6px |
| Form field vertical gap | 16px |
| Card padding (standard) | 16px |
| Card padding (dense/table) | 0 (table owns padding) |
| Card grid gap | 16px |
| Page section gap | 24px |
| Page horizontal padding | 24px (desktop), 16px (tablet/mobile) |
| Table cell padding | 8px 12px (dense) / 12px 16px (comfortable) |

## 2.8 Radius

| Token | Value | Usage |
|---|---|---|
| `--radius-xs` | 4px | Badges, chips, inline code |
| `--radius-sm` | 6px | Buttons, inputs |
| `--radius-md` | 8px | Cards, panels |
| `--radius-lg` | 12px | Modals, upload dropzone |
| `--radius-full` | 9999px | Avatars, status dots |

Do not use radii above 12px.

## 2.9 Borders & Elevation

InsightForge uses **borders, not shadows**, to separate surfaces. Elevation is communicated by background step (`bg-surface` → `bg-raised` → `bg-overlay`).

| Level | Treatment |
|---|---|
| Card | `bg-surface` + 1px `border-default`, no shadow |
| Popover / dropdown | `bg-raised` + 1px `border-default` + `0 8px 24px rgba(0,0,0,0.45)` |
| Modal | `bg-overlay` + 1px `border-default` + `0 16px 48px rgba(0,0,0,0.6)`; backdrop `rgba(5,6,8,0.7)` (no blur) |

## 2.10 Iconography

- Library: **Lucide** (`lucide-react`), 1.5px stroke.
- Sizes: 14px (inline/table), 16px (default), 20px (nav, empty states), 32px (empty-state illustrations).
- Icons inherit `currentColor`. Default `--text-tertiary`; active/hover `--text-primary`.
- Every icon-only button requires an `aria-label` and a tooltip.

Suggested mapping:

| Concept | Icon |
|---|---|
| Overview / Dashboard | `LayoutDashboard` |
| Projects | `FolderKanban` |
| Datasets | `Database` |
| Analysis | `FlaskConical` |
| Insights | `Lightbulb` |
| Reports | `FileText` |
| Power BI | `BarChart3` |
| Settings | `Settings` |
| SQL | `Terminal` |
| Customers | `Users` |
| Products | `Package` |
| Quality | `ShieldCheck` |
| Preparation | `Wand2` |
| EDA | `ScanSearch` |
| Evidence | `Link2` |
| Retry | `RotateCw` |

## 2.11 Number & Data Formatting

Formatting happens **only at the presentation layer**; raw values remain unmodified (PRD §114).

| Type | Rule | Example |
|---|---|---|
| Currency (INR default) | `₹` + Indian grouping; compact for KPI: `K`, `L`, `Cr` | `₹84.20L`, `₹1,24,500` |
| Currency (other) | From project `currency` metadata via `Intl.NumberFormat` | `$84,203` |
| Integers | Locale grouping | `125,430` |
| Percentages | 1 decimal place; 0 decimals if ≥ 100% | `51.7%` |
| Growth | Explicit sign + semantic color + arrow | `▲ +8.2%` / `▼ −3.1%` |
| Dates | ISO in tables (`2026-10-03`); friendly in headers (`3 Oct 2026`) | — |
| Durations | Human + exact on hover | `1.4 s` |
| Null / missing | Em dash `—` in `text-tertiary`, never `0` or `NaN` | `—` |
| Large counts | Compact above 1M in KPIs only | `1.25M` |

All numeric table columns are **right-aligned**, tabular, and mono-optional (use mono for IDs and SQL results).

---

# 3. Application Shell

## 3.1 Layout

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Sidebar (240px)  │ Top Bar (48px)                                    │
│                  ├───────────────────────────────────────────────────┤
│  Logo            │ Page Header (breadcrumb · title · actions)        │
│  ───────         │ ───────────────────────────────────────────────── │
│  Primary Nav     │                                                   │
│                  │ Content (max-width 1440px, centered)              │
│                  │                                                   │
│  ───────         │                                                   │
│  User / Project  │                                                   │
└──────────────────────────────────────────────────────────────────────┘
```

- Sidebar: fixed, `bg-subtle`, right border `border-subtle`.
- Top bar: sticky, `bg-base` at 92% with 1px bottom `border-subtle` (no blur).
- Content area scrolls; sidebar and top bar do not.
- Content `max-width: 1440px`; analytics tables and charts may bleed to full width within the container on screens above 1600px.

## 3.2 Sidebar

**Width:** 240px expanded · 56px collapsed (icon-only, tooltip on hover). Collapse state persisted per user.

Primary navigation (PRD §13, §99):

```text
[ ◆ InsightForge ]

OVERVIEW
  Overview
  Projects
  Datasets

ANALYSIS
  Analysis
  Insights
  Reports
  Power BI

────────────────
  Settings

[ avatar ] Sanskar
           user@email.com   ⋯
```

Item spec:
- Height 32px, padding `0 10px`, radius `--radius-sm`, icon 16px + 10px gap + label 13px/500.
- Default: `text-secondary`, no background.
- Hover: `bg-raised`, `text-primary`.
- Active: `accent-subtle` background, `text-primary`, **2px accent bar on the left edge**, icon in `--accent-500`.
- Focus-visible: 2px `accent-border` ring (offset 1px).
- Section labels use `text-overline`, `text-tertiary`, 16px top margin.

## 3.3 Project Sub-Navigation

Inside `/projects/[id]/*`, a **secondary horizontal tab bar** appears beneath the page header (not a second sidebar), per PRD §99:

```text
Overview · Dataset · Quality · Preparation · EDA · SQL · Customers · Products · Insights · Recommendations · Power BI · Reports
```

- Sticky under the top bar; horizontally scrollable on narrow widths with edge fade indicators.
- Each tab shows a **status dot** where relevant (see §3.4).
- Tabs for unavailable features (PRD §66) are shown in `text-disabled` with a lock icon and a tooltip explaining why; they remain clickable and lead to the explained Unavailable state.

## 3.4 Tab Status Indicators

| State | Indicator |
|---|---|
| Available / done | none (clean) |
| Processing | 6px amber pulsing dot |
| Failed | 6px danger dot |
| Unavailable | lock icon (12px) |
| New insights / unseen | 6px accent dot |

## 3.5 Top Bar

Left → right: collapse-sidebar toggle · breadcrumb · (spacer) · global search (`⌘K`, opens command palette) · notifications bell · help · user menu.

- Breadcrumb: `Projects / Retail Sales Analysis / Quality`, last item `text-primary`.
- Notifications (PRD §105): popover list with type icon, message, relative time, "Mark all read".
- Command palette (`⌘K`): searches Projects, Datasets, Insights, Reports (PRD §106) and offers navigation commands. Implemented as P2 but the UI hook exists in V1.

## 3.6 Page Header

```text
Projects / Retail Sales Analysis                         [ Secondary ] [ Primary ]
Data Quality
Explainable quality score and issues for dataset v2
```

- Title `text-h1`; description `text-body` `text-secondary`; actions right-aligned.
- Dataset-version selector chip (e.g., `v2 · Cleaned`) appears in the header of every analysis page, because every analysis references a dataset version (PRD §30). Changing it reloads the page for that version and shows a banner when viewing a non-latest version.

---

# 4. Component Library

Components live in `components/ui` (primitives) and `components/features` (domain). Every component documents: variants, sizes, all states, keyboard behavior, and ARIA.

## 4.1 Button

| Variant | Appearance | Use |
|---|---|---|
| Primary | `accent-500` bg, `on-accent` text | One per region: the main action |
| Secondary | `bg-raised`, 1px `border-default`, `text-primary` | Default actions |
| Ghost | transparent, hover `bg-raised` | Toolbar, tertiary |
| Danger | `danger` tint bg, `danger` text, border | Destructive (with confirmation) |
| Link | `text-primary`, underline on hover | Inline |

Sizes: `sm` 28px · `md` 32px (default) · `lg` 40px (auth/landing). Padding `0 12px` (md). Radius `--radius-sm`. Font 13px/500.

States: hover (lighter bg), pressed (darker; no scale transform), focus-visible (2px accent-border ring), disabled (`text-disabled`, 50% opacity, `not-allowed`), loading (spinner replaces icon, width locked, label stays).

## 4.2 Input / Textarea / Select

- Height 32px (md), 40px (auth). `bg-base`, 1px `border-default`, radius `--radius-sm`, padding `0 10px`.
- Focus: border `accent-500`, 3px `accent-subtle` ring.
- Error: border `danger`, message below in `danger` 12px with icon.
- Label above (12px/500 `text-secondary`); hint below (`text-tertiary`).
- Password fields include a show/hide toggle (accessible label).
- Select uses a custom listbox (Radix/Headless-style) with type-ahead; native select permitted on mobile.

## 4.3 Card

```text
┌──────────────────────────────────────────┐
│ Title                       [ actions ⋯ ] │  ← header 40px, border-subtle bottom
│ ──────────────────────────────────────── │
│ Content                                   │
│                                           │
│ Footer (optional: source · updated)       │
└──────────────────────────────────────────┘
```

- `bg-surface`, 1px `border-default`, radius `--radius-md`.
- Header: `text-h3` title + optional caption; actions on right (ghost icon buttons).
- **Every data card has an optional footer** showing source (e.g., `Source: sales_table · SUM(revenue)`) and an **Evidence** link (`Link2` icon) when it displays a verified metric.
- Interactive cards (clickable) show `border-strong` on hover and a 2px accent bar when selected.

## 4.4 KPI Card

```text
┌────────────────────────────┐
│ TOTAL REVENUE         ⓘ    │  overline label + info tooltip (definition)
│ ₹84.20L                     │  text-kpi, mono-tabular
│ ▲ +8.2% vs previous period  │  delta, semantic color
│ ▁▂▃▅▄▆▇ (sparkline)         │  optional, 24px tall, viz-1
└────────────────────────────┘
```

- Info tooltip shows the metric definition and calculation (e.g., `SUM(revenue)`), pulled from the metric record (PRD §49).
- Hover reveals "View evidence" link.
- Metrics with `Unavailable` state render a muted card with a lock icon and reason (see §6).
- Grid: 4 columns at ≥1280px, 2 at ≥768px, 1 below.

## 4.5 Badge / Status Chip

Height 20px, padding `0 6px`, radius `--radius-xs`, 11px/500, semantic tint background + 1px tinted border + optional 12px icon.

Mapped statuses:

| Domain | Values → Color |
|---|---|
| Project | DRAFT neutral · PROCESSING warning (pulse) · COMPLETED success · FAILED danger · ARCHIVED neutral-muted |
| Dataset | UPLOADED neutral · VALIDATING info · VALID success · INVALID danger · PROCESSING warning · READY success · FAILED danger |
| Analysis run | QUEUED neutral · RUNNING warning · COMPLETED success · FAILED danger · CANCELLED neutral-muted |
| Missingness severity | Low success · Moderate warning · High `#E08A3F`-tinted danger-light · Critical danger |
| Data handling | Detected info · Flagged warning · Removed neutral (PRD §26) |
| Confidence | High success · Medium warning · Low neutral |

## 4.6 Data Table

The most important component. Requirements (PRD §90):

- Server-side **pagination, sorting, filtering**, column visibility menu, and optional search.
- Sticky header, 1px `border-subtle` row dividers, hover row `bg-raised`.
- Header: `text-overline`, `text-tertiary`, sort indicator (chevron) on hover/active.
- Numeric columns right-aligned with tabular numerals; text left-aligned; status/badge centered or left.
- Density toggle: Dense (32px rows) / Comfortable (40px rows). Default Dense.
- Column resize and pinning: P2.
- Null display: `—`.
- Selected row: `accent-subtle` + left accent bar.
- Toolbar above table: search · filters (chips) · column menu · density · export.
- Footer: `Rows 1–50 of 125,430` · page-size select (25/50/100) · pagination controls.
- Never render more than 100 rows in the DOM without virtualization; virtualize above that.
- Empty/loading/error states per §6.

## 4.7 Tabs

- **Underline tabs** (primary): 36px height, 13px/500, active `text-primary` with 2px `accent-500` underline, inactive `text-secondary`.
- **Segmented control** (view toggles, e.g., Daily / Weekly / Monthly): `bg-base`, 1px `border-default`, active segment `bg-raised`.

## 4.8 Modal / Drawer / Popover / Tooltip

- Modal widths: sm 400 · md 560 · lg 760. Focus trap, `Esc` closes, returns focus to trigger.
- Drawer (right, 480px / 720px for evidence): used for **Evidence panel** and row details.
- Tooltip: `bg-overlay`, 12px, 6px/8px padding, 150ms delay, max-width 280px; never contains interactive content.
- Destructive confirmation modal requires typing the resource name for **project deletion** (PRD §108).

## 4.9 Toast

Bottom-right stack, max 3. 4s auto-dismiss (errors persist until dismissed). Left semantic icon, title + optional description + optional action (e.g., "View report"). `role="status"` (errors: `role="alert"`).

## 4.10 Progress Components

### Linear progress
4px track `border-default`, fill `accent-500`; determinate or indeterminate (a sliding segment, no gradient).

### Pipeline Stepper (PRD §61–62)

```text
Analysis in Progress                                         Run #3 · Dataset v2

✓ Uploaded ── ✓ Validated ── ✓ Profiled ── ✓ Cleaned ── ✓ EDA ── ⏳ SQL ── ○ Insights ── ○ Power BI ── ○ Reports ── ○ Deck
```

Stage states and icons:

| State | Icon | Color |
|---|---|---|
| Pending | hollow circle | `text-disabled` |
| Running | spinner / pulsing amber dot | `warning` |
| Complete | check in circle | `success` |
| Failed | alert-circle | `danger` |
| Skipped / Unavailable | dash in circle | `text-tertiary` |

- Horizontal at ≥1024px; vertical list below.
- Each stage is expandable to show its log (stage name, duration, key counts), mirroring worker logs (PRD §78).
- Failed stage reveals the **Error Panel** (§6.6).
- Polling/subscription updates animate state changes with a 150ms color transition only.

## 4.11 Upload Dropzone (PRD §17)

```text
┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐   dashed 1px border-strong, radius-lg
│                                         │
│            [ upload icon 32 ]           │
│          Drop dataset here              │
│       CSV · XLSX · JSON  ·  max 200 MB  │   (limit from config, PRD §76)
│            [ Browse files ]             │
│                                         │
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

States:
- **Idle:** as above.
- **Drag-over:** border `accent-500`, background `accent-subtle`, label "Release to upload".
- **Uploading:** file row with name, size, progress bar, percent, cancel.
- **Validating:** row shows stage list (extension → MIME → size → readability → structure → encoding).
- **Rejected:** `danger` banner with the specific reason (e.g., "File contains no usable rows." PRD §115) and "Choose another file".
- **Accepted:** success row with row/column counts and "Continue to preview".

Keyboard: dropzone is focusable, `Enter`/`Space` opens the file browser.

## 4.12 Feature Availability Banner (PRD §65–66, §116)

Used wherever a feature cannot run.

```text
┌──────────────────────────────────────────────────────────────────┐
│ 🔒  Customer Analysis is unavailable                              │
│     No customer identifier was detected in this dataset.          │
│     [ Review column mapping ]    [ Why is this needed? ]          │
└──────────────────────────────────────────────────────────────────┘
```

- Neutral tint, lock icon, **always states the reason and the remedy**.
- States: Available (no banner) · Unavailable (above) · Processing (info) · Failed (danger + Retry).

## 4.13 Insight Card

```text
┌──────────────────────────────────────────────────────────────────┐
│ [Revenue] [High confidence]                                  ⋯    │
│ High-value customers drive a large share of revenue               │  h3
│ High-value customers contribute 51.7% of total revenue while      │
│ representing 18% of customers.                                    │
│                                                                   │
│ ┌ Evidence ─────────────┐                                         │
│ │ Revenue share   51.7% │   Source: Customer segmentation (SQL)   │
│ │ Customer share  18.0% │                                         │
│ └───────────────────────┘                                         │
│ [ View evidence ]   [ Copy ]                                      │
└──────────────────────────────────────────────────────────────────┘
```

Rules:
- Every number in the description is rendered as a **MetricRef** (see §4.15) that links to evidence.
- Includes: Title, Description, Evidence, Metric, Source, Supporting Query, Confidence (PRD §50).
- Causal language is never styled as fact; correlation findings carry an **Association** badge with the tooltip "Association, not causation."

## 4.14 Recommendation Card

Same frame as the Insight Card with a distinct left border (`info`), fields: **Finding → Evidence → Recommendation (phrased as suggestion)**. Always shows a "Based on insight …" link. A small caption reads "Suggestion based on observed data; outcomes are not guaranteed" (PRD §52, §93).

## 4.15 MetricRef & Evidence Drawer

`MetricRef` is an inline numeric element: mono-tabular, `text-primary`, dotted underline in `border-strong`. Hover shows a tooltip (metric name, value, unit). Click opens the **Evidence Drawer** (right, 720px):

```text
Evidence · Total revenue
─────────────────────────────────────────────
Value        8,420,312.48   INR
Display      ₹84.20L
Dataset      v2 · Cleaned (sha: 3f9a…c21)
Pipeline     v1.0.3          Run #3
Calculated   2026-10-03 14:22 UTC

Calculation
  SUM(revenue)

Supporting SQL                           [ Copy ] [ Open in SQL ]
  SELECT SUM(revenue) AS total_revenue
  FROM transactions;

Result preview (5 rows)
  …
```

This drawer is the UI embodiment of the product's central principle (PRD §132): every conclusion is traceable.

## 4.16 SQL Editor / Result Panel (PRD §47–48)

- Code block: `bg-base`, 1px `border-default`, mono 12.5px, line numbers `text-disabled`, syntax colors drawn from the viz palette (keywords `viz-2`, functions `viz-1`, strings `viz-3`, numbers `viz-4`, comments `text-tertiary`).
- Read-only by default for generated queries; "Edit" opens a safe editor.
- Query toolbar: `Run` (primary) · `Copy` · `Format` · execution status badge · execution time.
- Client-side guard shows an inline `danger` message if the text contains `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, or `TRUNCATE`; the **server remains the authority**.
- Result table uses the standard Data Table with server pagination.
- Header strip: `Question` → `Generated SQL` → `Status` → `Result` → `Time`.

## 4.17 Charts (PRD §32, §91)

Library: **Recharts** or **Visx/ECharts** (decision recorded in `DECISIONS.md`); all charts wrapped in a single `<ChartFrame>` component.

`ChartFrame` provides: title, subtitle (grain, filters, dataset version), legend, tooltip, loading skeleton, empty/error states, "Evidence" link, "Download PNG/CSV" menu, and fullscreen.

Global rules:
- Background transparent over `bg-surface`; grid lines `border-subtle` (horizontal only for most charts); axis text 11–12px `text-tertiary`.
- Axes have **labels with units**; value axes start at zero for bar/area charts. Line charts may use a non-zero baseline but must visibly label it.
- Tooltip: `bg-overlay`, 1px border, shows exact (unrounded in context) value with unit; includes date/category header.
- Missing data: **gap in line**, never interpolated silently; footnote "n missing values excluded".
- Animation: initial draw 300ms ease-out; none on data updates > 500 points.
- Max points rendered per series ≈ 1,000; larger series are aggregated server-side (PRD §75). The chart subtitle reveals the aggregation grain.
- Pie/Donut only for ≤5 parts that sum to a whole; otherwise bar.
- No 3D, no shadows, no gradient fills (area charts use flat 12% opacity of series color).
- Accessible: every chart has a text summary (`aria-describedby`) and a "View as table" toggle.

Chart selection map (PRD §33):

| Data | Chart |
|---|---|
| Date × Revenue | Line (area optional) |
| Category × Revenue | Horizontal bar, sorted desc, top-N + "Other" |
| Numeric × Numeric | Scatter (with density/sampling for >5k points) |
| Numeric distribution | Histogram (+ optional box plot) |
| Category distribution | Bar |
| Correlation matrix | Heatmap (diverging scale) |
| Segment share | Donut (≤5) or stacked bar |

## 4.18 Empty State component

Centered, max-width 420px: 32px icon in `text-tertiary`, `text-h3` title, `text-body` explanation, 1–2 actions. No cartoon illustrations.

## 4.19 Skeleton

Block shapes matching final layout, `bg-raised` shimmering at `bg-overlay` (1.4s linear, translate-based, disabled under `prefers-reduced-motion`). Never use spinners for full page loads.

---

# 5. Page Specifications

Layouts use a **12-column grid**, 16px gutters, within the content container.

## 5.1 Landing Page — `/`

Purpose: explain the product precisely, then drive signup. This is the only place display typography is permitted.

Sections:

1. **Header** (64px): logo · Product · Workflow · Docs · `Sign in` (ghost) · `Get started` (primary).
2. **Hero** (two-column at ≥1024px):
   - Left: `InsightForge` overline; headline "Transform raw data into decisions." (`text-display`, solid `text-primary`, **no gradient**); subtext 2 lines; CTAs `Start an analysis` (primary) + `See how it works` (secondary).
   - Right: a **real product screenshot/mock** of the Executive Overview in a bordered frame (no floating 3D tilt).
3. **Workflow strip:** the pipeline `Raw Data → Preparation → Quality → EDA → SQL → Insights → Report → Deck` as a horizontal stepper with one-line descriptions.
4. **Principles grid (3 × 2):** Evidence before explanation · AI explains, analytics calculates · Reproducible · Transparent · Private by default · Extensible.
5. **Outputs section:** cards for Cleaned data, Quality report, EDA, SQL, Power BI model, PDF/DOCX report, PPTX deck.
6. **Trust section:** "Every number links to its calculation" with an animated-free Evidence Drawer mock.
7. **Footer:** product, docs, privacy, terms.

Motion: fade-in on scroll (opacity + 8px translate, 200ms, once). No parallax.

## 5.2 Login — `/login` (PRD §11)

```text
┌────────────────────────────┬────────────────────────────────────┐
│                            │                                    │
│   ◆ InsightForge           │        Welcome back                │
│                            │        Sign in to your workspace   │
│   Transform raw data       │                                    │
│   into decisions.          │        Email                       │
│                            │        [______________________]    │
│   (product preview /       │        Password         Forgot?    │
│    pipeline diagram)       │        [______________________]    │
│                            │        [      Sign In        ]     │
│                            │        ─────────  or  ─────────    │
│                            │        [ G  Continue with Google ] │
│                            │                                    │
│                            │        Don't have an account?      │
│                            │        Create account              │
└────────────────────────────┴────────────────────────────────────┘
```

- Split layout ≥1024px: left brand panel (`bg-subtle`, subtle dot-grid pattern at 4% opacity, pipeline diagram); right form panel, form width 360px, vertically centered.
- Below 1024px: brand panel hidden; compact logo above the form.
- Inputs `lg` (40px). Primary button full width. Google button secondary with the official Google "G" mark.
- Errors: inline field errors + form-level `danger` banner ("Incorrect email or password."). No account-enumeration hints.
- Expired session redirect shows an info banner: "Your session expired. Please sign in again." (PRD §12).
- Submit loading state locks the form.

## 5.3 Signup — `/signup`

Fields: Name, Email, Password (with strength meter: 4-segment bar, text label, requirements checklist), Confirm Password. Primary `Create account`, secondary Google. Link to Sign in. Terms/privacy consent line below the button.

## 5.4 Dashboard — `/dashboard` (PRD §14)

```text
Dashboard
Welcome back, Sanskar                          [ Upload dataset ] [ New analysis ]

┌ KPIs (5) ─────────────────────────────────────────────────────────┐
│ Projects  │ Datasets │ Completed analyses │ Reports │ Insights     │
└───────────────────────────────────────────────────────────────────┘

┌ Recent projects (8 cols) ───────────────────────┐ ┌ Quick actions (4) ┐
│ Name · Dataset · Status · Updated · Progress     │ │ New analysis      │
│ ...                                              │ │ Upload dataset    │
│                                                  │ │ View reports      │
└──────────────────────────────────────────────────┘ ├ Activity (4)  ────┤
                                                     │ Audit-style feed  │
                                                     └───────────────────┘
```

- KPI row: 5 compact KPI cards (no sparkline).
- Recent projects: table with progress as a thin 4px bar + percent; row click opens project; processing rows show the pulsing status badge and live progress.
- Activity feed (from audit events, PRD §79): "Analysis completed · Retail Sales Analysis · 2h ago".
- First-time user: dashboard shows a single large Empty State "Create your first project" with the 3-step explainer instead of zeroed KPI cards.

## 5.5 Projects List — `/projects`

- Header actions: `New project` (primary).
- Toolbar: search, status filter chips (Draft/Processing/Completed/Failed/Archived), sort, view toggle (table | cards).
- Table columns: Name · Dataset · Status · Rows · Quality score · Last updated · Owner-menu (⋯).
- Row menu: Open · Rename · Archive · Delete (confirmation, PRD §108).
- Pagination server-side (PRD §89).

## 5.6 New Project — `/projects/new` (PRD §16)

Centered form, 560px: Project name (required, 3–80 chars), Description (optional textarea, 500 chars, counter), Currency selector (default INR, stored as metadata, PRD §112), Domain selector (Retail/E-Commerce, disabled-others with "Coming soon" tooltip). Primary `Create project` → routes to `/projects/[id]/dataset` with the upload dropzone visible.

## 5.7 Project Overview — `/projects/[id]`

Purpose: single-glance status and the main entry to every analysis.

```text
Retail Sales Analysis                         [ Re-run analysis ] [ Generate report ▾ ]
[Status: COMPLETED] · Dataset v2 (Cleaned) · Updated 2h ago

┌ Pipeline stepper (full width) ────────────────────────────────────┐

┌ KPI strip: Revenue │ Orders │ Customers │ AOV ───────────────────┐

┌ Revenue trend (8 cols) ─────────────┐ ┌ Data quality (4 cols) ────┐
│ line chart, grain toggle            │ │ Score ring 87/100         │
│                                     │ │ 4 dimension bars          │
└─────────────────────────────────────┘ └───────────────────────────┘

┌ Feature availability grid (PRD §66) ──────────────────────────────┐
│ Sales ✓ │ Product ✓ │ Time ✓ │ Customer 🔒 │ RFM 🔒 │ Geography ✓  │
└───────────────────────────────────────────────────────────────────┘

┌ Top insights (6 cols) ──────────────┐ ┌ Artifacts (6 cols) ───────┐
│ 3 insight cards (compact)           │ │ Cleaned data · Report ·   │
│ [ View all insights ]               │ │ PPTX · Power BI model     │
└─────────────────────────────────────┘ └───────────────────────────┘
```

- During processing, the stepper is the dominant element and downstream sections show skeletons.
- On failure, the Error Panel (§6.6) appears above the stepper with Retry.
- Partial datasets show the availability grid with reasons.

## 5.8 Dataset — `/projects/[id]/dataset` (PRD §17–22)

Layout: left (8 cols) preview table; right (4 cols) metadata + version history.

- **Upload zone** (if no dataset) or **Dataset header**: filename, type badge, size, uploaded timestamp, checksum (mono, truncated with copy).
- **Summary strip:** Rows · Columns · Duplicates · Missing % · Size.
- **Schema table:** Column · Detected type (badge) · Semantic role (badge, editable select with "Validated" check, PRD §23) · Null % (mini bar) · Unique % · Min · Max · Mean · Median.
- **Preview table:** first N rows (default 100), virtualized, horizontal scroll with sticky first column.
- **Version panel (PRD §29–30, §118):** vertical timeline `v1 Original (immutable lock icon) → v2 Cleaned → v3 Transformed`, each with timestamp, operation count, "View lineage". Raw is labeled **Immutable**.
- Semantic mapping editor: changing a mapping requires `Apply` and triggers a clearly labeled re-analysis prompt; mapping confidence shown as a small bar.

## 5.9 Data Quality — `/projects/[id]/quality` (PRD §24–26, §117)

1. **Score header:** large score ring (96px) `87/100` + four dimension cards (Completeness, Consistency, Validity, Uniqueness) each with score, mini bar, and `?` tooltip describing the formula (documented in `ANALYTICS_SPEC.md`).
2. **"How is this calculated?"** expandable section: weights and formulas rendered as plain text + math.
3. **Missing data:** table of columns with null count, %, severity badge (Low/Moderate/High/Critical per PRD §25), plus a missingness-pattern heatmap.
4. **Duplicates:** three cards — Exact duplicates, Duplicate identifiers, Potential near-duplicates — each with count, status badge (Detected/Flagged/Removed), and "View records".
5. **Outliers:** list by column with method (IQR/Z-score/domain), count, status `Detected → Flagged → Explained`; **never** deleted by default; action menu to "Keep", "Flag", "Exclude from analysis" (versioned operation).
6. **Issue log:** *What was wrong → Records affected → What changed → Why* (PRD §117) as a table with severity filter.

Score ring: 8px stroke, track `border-default`, progress colored by threshold (≥85 success, 70–84 warning, <70 danger). Number in mono-tabular.

## 5.10 Data Preparation — `/projects/[id]/preparation` (PRD §27–30, §28)

- **Before/After summary:** two stat blocks `v1 Original → v2 Cleaned` (rows, columns, missing %, duplicates).
- **Cleaning log timeline:** each operation as a card:

```text
● Duplicate Removal                                   2026-10-03 14:20 UTC
  Before 125,430 rows → Removed 324 → After 125,106 rows
  Reason: Exact duplicate records                      [ View affected rows ]
```

- **Operations configurator** (for re-run): toggle list (remove exact duplicates, standardize types, normalize categories, handle missing, parse dates, normalize text, standardize numerics), each with parameters and a "preview impact" button showing counts before applying. Applying creates a **new dataset version**; nothing overwrites raw data.
- **Export:** cleaned dataset (CSV/XLSX).

## 5.11 EDA — `/projects/[id]/eda` (PRD §31–35)

Sub-sections via underline tabs: **Numerical · Categorical · Time · Correlation · Outliers**.

- **Numerical:** grid of per-column cards: histogram, summary stats (mean, median, std, min, max, quartiles). Column selector and search.
- **Categorical:** top-N bar charts + frequency tables with percentage contribution.
- **Time:** grain toggle (Daily/Weekly/Monthly/Yearly); revenue line with growth-rate sub-chart; growth table.
- **Correlation:** heatmap with method toggle (Pearson/Spearman). A persistent caption: "Correlation indicates association, not causation." Clicking a cell opens a scatter of the pair.
- **Outliers:** box plots + table of flagged records.
- Charts are only generated when meaningful (PRD §32); skipped charts are listed in a collapsed "Not generated (n)" section with reasons.

## 5.12 SQL Analysis — `/projects/[id]/sql` (PRD §46–48)

```text
┌ Question library (3 cols) ┐ ┌ Query workspace (9 cols) ───────────────────────┐
│ Sales                      │ │ Question: Which customers generate most revenue? │
│  • Revenue by month        │ │ ┌ SQL ──────────────────────────────────────┐   │
│  • AOV                     │ │ │ SELECT customer_id, SUM(revenue) ...       │   │
│ Customers                  │ │ └────────────────────────────────────────────┘   │
│  • Top customers           │ │ [ Run ]  Read-only · Executed · 184 ms · 50 rows │
│ Products …                 │ │ ┌ Result table ────────────────────────────┐    │
│ Time · Geography · Loyalty │ │ │ …                                          │    │
│ History                    │ │ └────────────────────────────────────────────┘   │
└────────────────────────────┘ │ [ Chart this result ] [ Export CSV ]              │
                               └──────────────────────────────────────────────────┘
```

- Left: categorized question library (Sales, Customers, Products, Categories, Time, Geography, Loyalty, Purchase behavior) + query history.
- Header banner (always visible): "Queries run in a read-only analytical environment." (PRD §48).
- Execution states: Idle · Running (progress + Cancel) · Succeeded · Failed (understandable message; no stack traces).
- "Chart this result" proposes a chart type using the selection map (§4.17).

## 5.13 Customer Analytics — `/projects/[id]/customers` (PRD §38–40)

If no customer identifier → full-page **Unavailable** state (§6.5).

Layout:
1. KPI strip: Total customers · New · Returning · Repeat purchase rate · Avg customer revenue · Avg orders/customer.
2. **Segmentation:** segment donut (fixed segment colors) + table (Segment · Customers · % customers · Revenue · % revenue · AOV). A visible **Rules** disclosure shows segmentation rules and the caption "Segments are rule-based classifications, not objective categories." (PRD §39)
3. **RFM:** 3×3 or 5×5 heatmap (Recency × Frequency, color = monetary), distribution histograms for R, F, M, and a customer table with `R · F · M · Score (e.g. 555) · Segment`.
4. **Loyalty / repeat behavior:** cohort or repeat-rate trend.
5. Customer detail drawer: orders over time, RFM values, segment, lifetime revenue.

## 5.14 Product Analytics — `/projects/[id]/products` (PRD §41)

- KPI strip: Products · Categories · Top product share · Top-10 contribution.
- Top / Bottom products (side-by-side horizontal bar charts, N selector).
- Category revenue & quantity (bar + table with contribution %).
- Pareto chart: cumulative revenue contribution by product.
- Product table with sorting/filtering and drawer detail.
- Discount, payment, and geography sub-tabs may live here or in a "Purchase Behavior" section: Discount level vs revenue/orders/AOV (with the **Association, not causation** note), Payment method (orders, revenue, AOV), Geography (country/state/city bar + table; a map is P2).

## 5.15 Insights — `/projects/[id]/insights` (PRD §50–51, §92)

- Toolbar: filter by theme (Sales, Customers, Products, Quality, Time), confidence, search; sort by impact/confidence.
- List of **Insight Cards** (§4.13), 2 columns on wide screens, 1 on narrow.
- Every card includes **View evidence** (drawer §4.15).
- Header note: "Insights are generated from verified metrics only."
- Empty state if the analysis is not complete; Partial state lists which insight categories are unavailable and why.

## 5.16 Recommendations — `/projects/[id]/recommendations` (PRD §52, §93)

- Grouped by priority or theme; each **Recommendation Card** (§4.14) links to its source insight and metric.
- Status controls (user-only): Open · In review · Done — stored as user metadata, never altering analytics.
- Persistent caption: suggestions, not guaranteed outcomes.

## 5.17 Power BI — `/projects/[id]/powerbi` (PRD §55–57)

Sections:
1. **Star schema diagram:** read-only ERD (fact_sales in the center; dim_customer, dim_product, dim_date, dim_location, dim_payment around it) with column lists on click.
2. **Measures table:** Name · DAX expression · Description · Availability.
3. **Dashboard specification:** five page cards (Executive Overview, Customer Analytics, Product Analytics, Purchase Behavior, Geography) each with wireframe thumbnail, visuals list, and fields required; unavailable visuals marked with reasons.
4. **Downloads:** model package (CSV/Parquet per table), measures file, dashboard spec (PDF/MD). Instructions panel: "Import into Power BI Desktop" steps. Direct publishing is explicitly noted as out of scope for V1.

## 5.18 Reports — `/projects/[id]/reports` (PRD §58–60)

- **Generate panel:** format cards — PDF, DOCX, PPTX — each with a section checklist (Cover, Executive Summary, Dataset Overview, Data Quality, Data Preparation, EDA, SQL, Customers, Products, Sales, Insights, Recommendations, Limitations, Appendix). Unavailable sections disabled with reasons.
- **Generation progress:** uses the Pipeline Stepper in compact mode; completion triggers a toast with a download action.
- **History table:** Format · Dataset version · Run · Generated · Size · Download · Delete. Downloads are audited (PRD §79).
- **Limitations preview:** shows the relevant limitations that will be included (PRD §94) so users aren't surprised.

## 5.19 Global Pages

### Datasets — `/datasets`
Cross-project dataset table (Name · Project · Rows · Columns · Status · Uploaded). Deletion checks dependencies and lists affected analyses before confirming (PRD §109).

### Analysis — global
Cross-project list of analysis runs with status, dataset version, pipeline version, duration, and retry action.

### Reports — `/reports`
Cross-project report history.

### Power BI — `/powerbi`
Cross-project model packages.

### Settings — `/settings`

Left sub-nav (Profile · Security · Preferences · Data & Retention · API/Integrations · Danger zone):
- **Profile:** name, email, avatar.
- **Security:** change password (if local), connected Google account, active sessions with revoke, sign out everywhere.
- **Preferences:** default currency, number format, default table density, theme (dark; light disabled "coming soon"), notification toggles.
- **Data & Retention:** retention policy display/config for datasets, generated files, temp files, failed jobs (PRD §110); export all data.
- **Danger zone:** delete account (typed confirmation).

---

# 6. State Design (PRD §72)

Every data-bearing screen implements all eight states. A shared `<AsyncBoundary>` standardizes behavior.

## 6.1 Loading / Skeleton

- Show a **skeleton matching the final layout** within 100ms; never a blank page or centered spinner for page-level loads.
- Charts show a skeleton chart frame with axes placeholders.
- If a load exceeds 8s, add a subtle "Still working…" caption.

## 6.2 Empty

Specific, actionable copy: *"No datasets yet — upload a CSV, XLSX or JSON file to start."* + primary action.

## 6.3 Success

Transient confirmation via toast; persistent state expressed via badges, not banners.

## 6.4 Processing

- Stepper + disabled dependent sections showing skeletons with the label "Waiting for SQL analysis…".
- Users can navigate away; a persistent mini progress chip stays in the top bar (`Analysis 62%`).
- Page auto-updates (polling or SSE) without full reload (PRD §63, §75).

## 6.5 Unavailable / Partial (PRD §65–66, §116)

- **Unavailable (whole feature):** centered panel with lock icon, title ("RFM analysis unavailable"), reason ("A transaction date and customer identifier are required."), and remedies (`Review column mapping`, `Upload a different dataset`).
- **Partial:** the page renders what can be computed; each missing module is replaced with an inline availability banner (§4.12). A summary chip at the top: `Partial analysis · 3 modules unavailable`.

## 6.6 Error / Retry (PRD §64, §103)

Error Panel:

```text
┌──────────────────────────────────────────────────────────────────┐
│ ⚠  SQL analysis failed                                            │
│    The dataset was cleaned successfully, but SQL analysis could   │
│    not be completed.                                              │
│                                                                   │
│    Reason: Required customer identifier was not detected.         │
│                                                                   │
│    [ Retry ]  [ View details ]  [ Review column mapping ]         │
└──────────────────────────────────────────────────────────────────┘
```

- Plain language; no stack traces (PRD §64). "View details" shows a **sanitized** error code, stage, timestamp, and a copyable reference ID.
- Retry is idempotent (PRD §103–104): the button is disabled while a retry is in flight, and the UI reflects the same run if one already exists.
- Network errors: inline "Couldn't load. Retry" per card, so one failed widget doesn't blank the page.
- Authorization errors: 403 page "You don't have access to this resource." with a link home; 404 for resources the user doesn't own (no existence leakage).

## 6.7 Stale / Version states

A banner appears when viewing an older dataset version: "You're viewing v1 (Original). Latest is v3. [ Switch to latest ]". Cached results are always keyed by dataset version (PRD §77).

---

# 7. Motion

Motion is functional only.

| Token | Duration | Easing | Use |
|---|---|---|---|
| `--motion-instant` | 80ms | linear | Hover color |
| `--motion-fast` | 120ms | `cubic-bezier(0.2, 0, 0, 1)` | Buttons, toggles |
| `--motion-base` | 180ms | `cubic-bezier(0.2, 0, 0, 1)` | Dropdowns, drawers (translate 8px + fade) |
| `--motion-slow` | 300ms | `cubic-bezier(0.2, 0, 0, 1)` | Chart initial draw, modal enter |

Rules:
- Animate only `opacity`, `transform`, `background-color`, `border-color`, `color`. Never animate layout properties (`width`, `height`) except progress fills.
- No bouncing, springs, parallax, or looping decorative animations. Allowed loops: skeleton shimmer, spinner, 6px "processing" dot pulse (1.6s).
- **`prefers-reduced-motion`:** disable shimmer, transforms, chart draw; keep only opacity fades ≤ 100ms.
- Page transitions: none (instant route changes with skeleton).

---

# 8. Responsive Behavior (PRD §73)

| Breakpoint | Name | Behavior |
|---|---|---|
| ≥1536px | 2xl | Content max 1440px, centered; wide tables may use full width |
| ≥1280px | xl | Full layout; 4-column KPI grids; 12-col grid |
| ≥1024px | lg | Sidebar expanded; two-column pages remain |
| ≥768px | md | Sidebar collapses to 56px icon rail; KPI 2-col; side panels stack under main content |
| <768px | sm | Sidebar becomes off-canvas drawer (hamburger in top bar); single column; project tab bar scrolls horizontally |

Specifics:
- **Tables:** become horizontally scrollable inside their card; first column sticky; optional per-table "card list" transform for ≤640px is P2. Page body never scrolls sideways.
- **Charts:** height adapts (min 220px); legends move below; tooltips are tap-activated; dense axis labels rotate or thin out.
- **Drawers:** become full-screen sheets below 768px.
- **Modals:** become bottom sheets below 640px.
- **Touch targets:** ≥ 40px on touch devices (inputs/buttons increase from 32 → 40px at `sm`).
- Desktop remains the optimized target; mobile must be fully usable but may prioritize reading over authoring (e.g., SQL editing is read-first on mobile).

---

# 9. Accessibility (PRD §74)

Target: **WCAG 2.2 AA**.

- **Contrast:** `text-primary` on `bg-surface` ≈ 14:1; `text-secondary` ≥ 7:1; `text-tertiary` (#6E7887) used for non-essential text only and verified ≥ 4.5:1 on `bg-surface`/`bg-base` (adjust token if audit fails). Accent on `bg-base` ≥ 7:1; `on-accent` on accent ≥ 9:1. UI component borders needed to identify controls ≥ 3:1 (inputs use `border-strong` if `border-default` fails audit).
- **Keyboard:** full keyboard operation; logical tab order; visible focus (2px `accent-border` ring + 1px offset) on every interactive element; skip-to-content link; `Esc` closes overlays; arrow-key navigation in tabs, menus, listboxes, and tables with row selection.
- **Semantics:** landmarks (`header`, `nav`, `main`, `aside`), one `h1` per page, headings in order, real `<table>` markup with `<th scope>`, `<button>` vs `<a>` used correctly.
- **Labels:** every input has a programmatic label; icon-only controls have `aria-label`; form errors linked with `aria-describedby` and announced.
- **Live regions:** job progress changes announced via `aria-live="polite"`; errors via `role="alert"`; toasts as above.
- **Charts:** text alternative + "View as table"; color never the sole encoding; patterns/markers/direct labels supported; keyboard-focusable data points are P2, table fallback is P0.
- **Motion:** respect `prefers-reduced-motion` (see §7).
- **Zoom/reflow:** usable at 200% zoom and 320px width without two-dimensional scrolling (data tables excepted).
- **Language:** `lang="en"`; copy at ≤ grade-10 reading level where feasible.
- **Testing:** automated axe checks in CI on all pages/states; manual keyboard and screen-reader passes before release.

---

# 10. Content & Voice

- **Tone:** precise, calm, plainspoken. No hype, no exclamation marks, no emoji, no "magic/AI-powered" language.
- **Verbs:** action-first button labels: `Upload dataset`, `Run analysis`, `Generate report`, `View evidence`.
- **Errors:** what happened → why → what to do. Never blame the user. No stack traces.
- **Uncertainty:** use "suggests", "is associated with", "may warrant investigation". Avoid "causes", "proves", "will increase" (PRD §92, §93).
- **Numbers in copy:** always sourced from verified metrics via `MetricRef`; never hand-typed into UI strings (PRD §126).
- **Empty-state copy** names the next action.
- **Units** always shown (currency symbol, %, rows).
- **AI-generated text** (summaries, SQL assistance) carries a small `AI-assisted` tag with a tooltip: "Explains verified results. Numbers come from the analytics engine." (PRD §53, §97).

---

# 11. Implementation Guidance

## 11.1 Tailwind theme (excerpt)

```ts
// tailwind.config.ts
import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "var(--bg-base)",
          subtle: "var(--bg-subtle)",
          surface: "var(--bg-surface)",
          raised: "var(--bg-raised)",
          overlay: "var(--bg-overlay)",
        },
        border: {
          subtle: "var(--border-subtle)",
          DEFAULT: "var(--border-default)",
          strong: "var(--border-strong)",
        },
        text: {
          primary: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          tertiary: "var(--text-tertiary)",
          disabled: "var(--text-disabled)",
        },
        accent: {
          400: "var(--accent-400)",
          500: "var(--accent-500)",
          600: "var(--accent-600)",
          subtle: "var(--accent-subtle)",
          border: "var(--accent-border)",
          on: "var(--on-accent)",
        },
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
        info: "var(--info)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "SF Mono", "Menlo", "monospace"],
      },
      fontSize: {
        display: ["28px", { lineHeight: "34px", letterSpacing: "-0.02em", fontWeight: "600" }],
        h1: ["22px", { lineHeight: "28px", letterSpacing: "-0.01em", fontWeight: "600" }],
        h2: ["17px", { lineHeight: "24px", fontWeight: "600" }],
        h3: ["14px", { lineHeight: "20px", fontWeight: "600" }],
        body: ["13px", { lineHeight: "20px" }],
        "body-lg": ["14px", { lineHeight: "22px" }],
        caption: ["12px", { lineHeight: "16px" }],
        overline: ["11px", { lineHeight: "14px", letterSpacing: "0.06em", fontWeight: "500" }],
        kpi: ["28px", { lineHeight: "32px", letterSpacing: "-0.02em", fontWeight: "600" }],
        "kpi-sm": ["20px", { lineHeight: "24px", letterSpacing: "-0.01em", fontWeight: "600" }],
      },
      borderRadius: { xs: "4px", sm: "6px", md: "8px", lg: "12px" },
      transitionTimingFunction: { out: "cubic-bezier(0.2, 0, 0, 1)" },
    },
  },
} satisfies Config;
```

## 11.2 Global CSS tokens (excerpt)

```css
:root {
  --bg-base: #0B0D10;      --bg-subtle: #0F1216;   --bg-surface: #14181D;
  --bg-raised: #1A1F26;    --bg-overlay: #212731;
  --border-subtle: #1F252D; --border-default: #2A313B; --border-strong: #3A424F;
  --text-primary: #E8EBEF; --text-secondary: #A3ACB9;
  --text-tertiary: #6E7887; --text-disabled: #4A525E;
  --accent-400: #EDB45E;   --accent-500: #E8A33D;  --accent-600: #C98724;
  --accent-subtle: rgba(232,163,61,0.12);
  --accent-border: rgba(232,163,61,0.35);
  --on-accent: #15100A;
  --success: #3FB68B; --warning: #E0B341; --danger: #E5645A; --info: #5B9BD5;
  --viz-1: #E8A33D; --viz-2: #5B9BD5; --viz-3: #3FB68B; --viz-4: #B58AE0;
  --viz-5: #E5645A; --viz-6: #4FC1C7; --viz-7: #C9C14A; --viz-8: #8A94A6;
}
html { color-scheme: dark; background: var(--bg-base); color: var(--text-secondary); }
body { font-feature-settings: "cv11" 1; -webkit-font-smoothing: antialiased; }
.tnum { font-variant-numeric: tabular-nums; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

## 11.3 Component directory

```text
components/
  ui/                 # primitives
    button.tsx  input.tsx  select.tsx  textarea.tsx  badge.tsx  card.tsx
    tabs.tsx  segmented.tsx  tooltip.tsx  popover.tsx  modal.tsx  drawer.tsx
    toast.tsx  skeleton.tsx  progress.tsx  data-table/  empty-state.tsx
  features/           # domain components
    app-shell/  sidebar.tsx  topbar.tsx  project-tabs.tsx  command-palette.tsx
    upload/     dropzone.tsx  validation-list.tsx
    pipeline/   pipeline-stepper.tsx  error-panel.tsx  availability-banner.tsx
    metrics/    kpi-card.tsx  metric-ref.tsx  evidence-drawer.tsx
    insights/   insight-card.tsx  recommendation-card.tsx
    sql/        sql-editor.tsx  result-panel.tsx  question-library.tsx
    charts/     chart-frame.tsx  line.tsx  bar.tsx  histogram.tsx  scatter.tsx
                heatmap.tsx  donut.tsx  box-plot.tsx
    quality/    score-ring.tsx  severity-badge.tsx  issue-log.tsx
    dataset/    schema-table.tsx  version-timeline.tsx  mapping-editor.tsx
    powerbi/    star-schema.tsx  measures-table.tsx  page-spec-card.tsx
  async-boundary.tsx
```

## 11.4 Engineering rules

- Components use **tokens only**; raw hex and arbitrary Tailwind values are lint-errors (`no-restricted-syntax` / custom ESLint rule).
- Every component ships with a Storybook (or equivalent) story covering all variants and states, plus an axe check.
- Primitives are headless-accessible (Radix UI or equivalent) and styled via Tailwind; no ad-hoc re-implementation of dialogs, menus, or listboxes.
- Server data via a typed API client (generated from `API_SPEC.md`); all list endpoints paginated (PRD §89).
- Never render raw API errors; map error codes to copy.
- Charts receive pre-aggregated data; the client must not receive raw millions of rows (PRD §20, §75).
- Visual regression tests for key pages in each primary state (Success, Empty, Error, Processing, Partial).

---

# 12. Design Acceptance Checklist

A screen is **design-complete** only when all are true:

- [ ] Uses only tokens (color, spacing, type, radius) — no raw values
- [ ] Implements Loading/Skeleton, Empty, Success, Error, Processing, Partial, Retry
- [ ] Every displayed metric has a MetricRef and reachable evidence (where applicable)
- [ ] Unavailable features explain **why** and offer a remedy
- [ ] Numbers are formatted per §2.11 with tabular numerals; nulls show `—`
- [ ] Charts have titles, axis labels with units, tooltips, text alternative and table view
- [ ] No gradients, glows, glassmorphism, or decorative animation
- [ ] Accent used sparingly (≤ 1 primary action per region)
- [ ] Keyboard-only walkthrough passes; focus always visible
- [ ] axe reports zero serious/critical issues
- [ ] Works at 1440, 1024, 768, and 390px widths without page-level horizontal scroll
- [ ] `prefers-reduced-motion` honored
- [ ] Copy follows §10 (no causal claims, no stack traces, no hype)
- [ ] Dataset version context visible on every analysis view

---

# 13. Traceability to PRD

| PRD Section | Design Section |
|---|---|
| §11–12 Authentication | §5.2, §5.3 |
| §13, §99 Navigation | §3.2, §3.3 |
| §14 Dashboard | §5.4 |
| §16 Project creation | §5.6 |
| §17–20 Upload, validation, preview | §4.11, §5.8 |
| §21–23 Profiling, types, semantics | §5.8 |
| §24–26 Quality, missing, duplicates | §5.9 |
| §27–30 Cleaning, versioning | §5.10, §3.6 |
| §31–35 EDA | §5.11, §4.17 |
| §36–45 Retail analytics | §5.13, §5.14 |
| §46–48 SQL | §4.16, §5.12 |
| §49–52 Metrics, insights, recommendations | §4.13–4.15, §5.15, §5.16 |
| §55–57 Power BI | §5.17 |
| §58–60 Reports | §5.18 |
| §61–66 Status, progress, errors, partial | §4.10, §4.12, §6 |
| §70–74 Frontend, states, responsive, a11y | §6, §8, §9 |
| §91 Charts | §4.17 |
| §98 Design requirements | §1, §2 |
| §112–114 Currency, precision | §2.11 |
| §126 Prohibited shortcuts | §1.3, §10, §11.4 |
