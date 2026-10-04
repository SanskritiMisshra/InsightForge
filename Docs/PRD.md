# InsightForge — Product Requirements Document (PRD)

**Version:** 1.0
**Status:** Approved for Development
**Product:** InsightForge
**Document Owner:** Product / Engineering
**Primary Platform:** Web Application
**Primary Domain:** Data Analytics & Business Intelligence
**Initial Dataset Domain:** Retail / E-Commerce
**Target Architecture:** Next.js + TypeScript + FastAPI + Python Analytics Engine + PostgreSQL + Redis + Celery

---

# 1. Product Overview

## 1.1 Product Name

**InsightForge**

## 1.2 Product Tagline

> Transform raw data into decisions.

## 1.3 Product Description

InsightForge is a web-based, end-to-end data analytics and business intelligence platform that allows users to upload structured datasets and transform them into:

- Cleaned and validated datasets
- Data-quality assessments
- Exploratory Data Analysis (EDA)
- Statistical analysis
- SQL-based business analysis
- Customer segmentation
- Product and sales analysis
- Purchase-driver analysis
- Power BI-ready analytical models
- Interactive visualizations
- Evidence-backed business insights
- Business recommendations
- Executive reports
- Presentation decks

The platform combines the complete analytics workflow into one product:

```text
Raw Dataset
    ↓
Data Preparation
    ↓
Data Quality
    ↓
Data Modeling
    ↓
Exploratory Data Analysis
    ↓
SQL Analysis
    ↓
Business Intelligence
    ↓
Power BI
    ↓
Insights
    ↓
Recommendations
    ↓
Report
    ↓
Presentation
```

---

# 2. Product Vision

## 2.1 Vision

Build a professional analytics platform that allows a user with a structured dataset to move from raw data to evidence-backed business decisions without manually performing every repetitive analytics task.

The platform should demonstrate the complete lifecycle of a modern data analytics project while remaining technically sound, reproducible, explainable, and extensible.

---

# 3. Problem Statement

Data analysts commonly need to perform the following tasks separately:

1. Collect a dataset.
2. Inspect its structure.
3. Clean missing and invalid data.
4. Detect duplicates.
5. Identify data types.
6. Transform the dataset.
7. Perform exploratory analysis.
8. Write SQL queries.
9. Segment customers.
10. Analyze products.
11. Analyze sales trends.
12. Build dashboards.
13. Identify important findings.
14. Write recommendations.
15. Prepare reports.
16. Prepare presentations.

These activities often involve multiple tools and repeated manual work.

InsightForge brings these activities into one structured workflow.

---

# 4. Product Goal

The primary goal is:

> Allow a user to upload a supported structured dataset and receive a complete, traceable analytics workspace containing data-quality results, cleaned data, EDA, SQL analysis, visualizations, insights, recommendations, and downloadable reports.

---

# 5. Product Principles

InsightForge must follow these principles.

## 5.1 Accuracy over appearance

A beautiful dashboard with incorrect analytics is considered a failed product.

## 5.2 Evidence before explanation

Every numerical insight must originate from deterministic analytical calculations.

## 5.3 AI explains; analytics calculates

Python, SQL, statistics, and deterministic analytical functions are the source of numerical truth.

An LLM may explain verified results but must not invent metrics.

## 5.4 Reproducibility

An analysis must be reproducible from:

- Dataset version
- Cleaning operations
- Transformation configuration
- Analysis configuration
- SQL queries
- Analytics engine version

## 5.5 Transparency

Users should be able to understand:

- What was changed
- Why it was changed
- Which calculations were performed
- Where an insight came from

## 5.6 Extensibility

V1 focuses on retail/e-commerce analytics, but the architecture must allow additional domains later.

---

# 6. Target Users

## 6.1 Primary Users

### Students

Students who need to perform complete analytics projects involving:

- Python
- SQL
- Power BI
- EDA
- Reports

### Data Analysts

Analysts who want to accelerate repetitive exploratory analysis.

### Business Analysts

Users who need business-oriented insights from structured datasets.

### Researchers

Users who need quick dataset profiling and exploratory analysis.

### Small Businesses

Users who want to understand sales and customer data without building an analytics pipeline from scratch.

---

# 7. User Personas

## Persona 1 — Student

**Name:** Analytics Student

**Goal:** Complete a professional analytics project.

**Needs:**

- Data cleaning
- EDA
- SQL
- Power BI
- Report
- Presentation

**Pain point:** Needs to manually perform the same repetitive analysis steps.

---

## Persona 2 — Junior Data Analyst

**Goal:** Quickly understand a new dataset.

**Needs:**

- Automated profiling
- Data quality
- EDA
- SQL
- Visualization

**Pain point:** Spends significant time on repetitive exploratory analysis.

---

## Persona 3 — Business User

**Goal:** Understand business performance.

**Needs:**

- KPIs
- Trends
- Customer segments
- Product performance
- Recommendations

**Pain point:** Raw datasets are difficult to interpret.

---

# 8. V1 Product Scope

V1 must focus on one primary domain:

> **Retail / E-Commerce**

Supported file formats:

- CSV
- XLSX
- JSON

V1 should support datasets containing common fields such as:

```text
customer_id
transaction_id
product_id
product_name
category
quantity
price
revenue
discount
purchase_date
customer_age
gender
city
country
payment_method
```

The system must not assume every dataset contains all of these fields.

---

# 9. V1 Non-Goals

The following are explicitly outside V1 scope.

## 9.1 Universal Dataset Intelligence

V1 must NOT promise perfect automated analysis of every possible dataset.

## 9.2 Real-time Streaming Analytics

No Kafka-based real-time analytics in V1.

## 9.3 Enterprise Data Warehousing

No Snowflake/BigQuery/Databricks integration required in V1.

## 9.4 Full Power BI Cloud Automation

V1 should generate Power BI-ready analytical models/data and provide the required dashboard specification.

Direct automated publishing to a user's Power BI tenant is not required for V1.

## 9.5 Advanced Machine Learning

Predictive ML is not a core V1 feature.

Basic statistical analysis and customer segmentation are sufficient.

## 9.6 Fully Autonomous Business Decisions

InsightForge must provide evidence-backed recommendations.

It must not claim certainty about business decisions.

---

# 10. Product Workflow

The complete workflow is:

```text
User
 ↓
Authentication
 ↓
Dashboard
 ↓
Create Project
 ↓
Upload Dataset
 ↓
Validate Dataset
 ↓
Profile Dataset
 ↓
Assess Data Quality
 ↓
Clean Dataset
 ↓
Transform Dataset
 ↓
Detect Semantic Meaning
 ↓
Perform EDA
 ↓
Load Analytical Data
 ↓
Perform SQL Analysis
 ↓
Generate Business Metrics
 ↓
Generate Insights
 ↓
Generate Recommendations
 ↓
Generate Power BI Model
 ↓
Generate Report
 ↓
Generate Presentation
```

---

# 11. Authentication

## 11.1 Login Methods

V1 must support:

- Email/password authentication
- Google OAuth

## 11.2 Login Page

The login page must contain:

```text
InsightForge

Email
[________________]

Password
[________________]

[ Sign In ]

[ Continue with Google ]

Forgot Password?

Don't have an account?
Create Account
```

## 11.3 Signup

Fields:

```text
Name
Email
Password
Confirm Password
```

Google signup must also be supported.

---

# 12. Authentication Requirements

The system must:

- Secure passwords using a proper password hashing mechanism if locally managed.
- Never store plaintext passwords.
- Use secure sessions/tokens.
- Protect authenticated routes.
- Prevent unauthorized resource access.
- Support logout.
- Handle expired sessions.
- Handle authentication failures gracefully.

---

# 13. Application Navigation

After authentication, the application must provide:

```text
Dashboard
Projects
Datasets
Analysis
Reports
Power BI
Settings
```

Primary navigation should be persistent.

---

# 14. Dashboard

The dashboard is the main application landing page after login.

## 14.1 Dashboard Requirements

Display:

### Overview Metrics

```text
Total Projects
Total Datasets
Completed Analyses
Generated Reports
Generated Insights
```

### Recent Projects

Each project should display:

```text
Project Name
Dataset Name
Status
Last Updated
Analysis Progress
```

### Quick Actions

```text
New Analysis
Upload Dataset
View Reports
```

---

# 15. Project Concept

A project is the top-level container for an analytics workflow.

Example:

```text
Project:
Retail Sales Analysis 2026
```

A project contains:

```text
Dataset
Dataset Versions
Analysis Runs
Metrics
Insights
Recommendations
SQL Queries
Reports
Presentations
Power BI Models
```

---

# 16. Project Creation

The user must be able to create:

```text
Project Name
Description
```

Example:

```text
Name:
Retail Sales Analysis

Description:
Analysis of customer purchasing behavior and sales performance.
```

---

# 17. Dataset Upload

Users must be able to upload:

- CSV
- XLSX
- JSON

## 17.1 Upload UI

The interface should support:

- Drag and drop
- File browser
- Upload progress
- File validation
- Error messages

Example:

```text
Upload Dataset

┌─────────────────────────────────┐
│                                 │
│       Drop dataset here         │
│                                 │
│      CSV • XLSX • JSON          │
│                                 │
│       [ Browse Files ]          │
│                                 │
└─────────────────────────────────┘
```

---

# 18. File Validation

Before processing, the system must validate:

- File extension
- MIME type
- File size
- File readability
- Dataset structure
- Encoding where applicable
- Corrupted files

Invalid files must not enter the analytics pipeline.

---

# 19. Dataset Metadata

After successful upload, store:

```text
Dataset ID
Project ID
Original filename
File type
File size
Upload timestamp
Row count
Column count
Dataset checksum
Processing status
```

---

# 20. Dataset Preview

Users must be able to preview the dataset.

Display:

```text
Rows
Columns
First N rows
Column names
Detected data types
Missing values
Unique values
```

Example:

```text
125,430 rows
18 columns

customer_id     string
age             integer
revenue         float
purchase_date   datetime
category        categorical
```

The entire raw dataset must not be loaded into the browser.

Preview only a limited number of rows.

---

# 21. Dataset Profiling

After upload, the platform must automatically profile the dataset.

The profiler should calculate:

## Dataset-level metrics

- Number of rows
- Number of columns
- Memory/file size where applicable
- Duplicate row count
- Missing value count
- Overall missing percentage

## Column-level metrics

- Data type
- Null count
- Null percentage
- Unique count
- Unique percentage
- Minimum
- Maximum
- Mean
- Median
- Standard deviation
- Percentiles where applicable

---

# 22. Data Type Detection

The system should classify columns as:

```text
INTEGER
FLOAT
NUMERIC
BOOLEAN
DATE
DATETIME
CATEGORICAL
TEXT
IDENTIFIER
```

Data type detection must be deterministic where possible.

---

# 23. Semantic Column Detection

The platform should attempt to identify business roles.

Examples:

```text
customer_id    → CUSTOMER_ID
transaction_id → TRANSACTION_ID
product_id     → PRODUCT_ID
revenue        → REVENUE
price          → PRICE
quantity       → QUANTITY
discount       → DISCOUNT
purchase_date  → PURCHASE_DATE
```

Semantic mapping should combine:

- Column names
- Data types
- Value patterns
- Cardinality
- Domain rules

AI may assist with ambiguous semantic mapping, but the final mapping must be validated.

---

# 24. Data Quality Assessment

The platform must calculate a data-quality score.

Example dimensions:

```text
Completeness
Consistency
Validity
Uniqueness
Accuracy indicators
```

The score must be explainable.

Example:

```text
Data Quality Score: 87/100

Completeness: 91
Consistency: 94
Validity: 96
Uniqueness: 78
```

The exact scoring methodology must be documented in `ANALYTICS_SPEC.md`.

---

# 25. Missing Data Analysis

Detect:

- Missing values
- Missing percentage
- Missing patterns
- Columns with high missingness

The system should categorize missingness severity.

Example:

```text
0–5%       Low
5–20%      Moderate
20–50%     High
>50%       Critical
```

These thresholds are configurable.

---

# 26. Duplicate Detection

Detect:

### Exact duplicates

Rows that are completely identical.

### Duplicate identifiers

Example: `transaction_id` appearing multiple times.

### Potential duplicate records

Records that are highly similar.

The platform should distinguish between:

```text
Detected
Flagged
Removed
```

---

# 27. Data Cleaning

The cleaning engine must perform safe transformations.

Possible operations:

- Remove exact duplicates
- Standardize data types
- Normalize categorical values
- Handle missing values
- Parse dates
- Remove invalid records when justified
- Normalize text
- Standardize numeric formats

Every operation must be recorded.

---

# 28. Cleaning Log

Each transformation must create a log entry.

Example:

```text
Cleaning Operation

Type:
Duplicate Removal

Before:
125,430 rows

Removed:
324 rows

After:
125,106 rows

Reason:
Exact duplicate records

Timestamp:
2026-10-03
```

---

# 29. No Destructive Raw Data Changes

The original uploaded dataset must remain immutable.

The system must maintain:

```text
Raw Dataset
    ↓
Dataset Version
    ↓
Clean Dataset
```

The original data must never be overwritten.

---

# 30. Dataset Versioning

Every dataset modification should create a new version.

Example:

```text
Version 1
Original Dataset

Version 2
After Cleaning

Version 3
After Transformation
```

Each analysis run must reference a specific dataset version.

---

# 31. Exploratory Data Analysis

The platform must automatically generate EDA.

## Numerical analysis

Generate:

- Mean
- Median
- Standard deviation
- Min
- Max
- Quartiles
- Distribution

## Categorical analysis

Generate:

- Frequency
- Top categories
- Category count
- Percentage contribution

## Time analysis

Where dates exist:

- Daily trends
- Weekly trends
- Monthly trends
- Yearly trends
- Growth rates

---

# 32. EDA Visualizations

Depending on the dataset, generate appropriate charts.

Possible charts:

```text
Bar Chart
Line Chart
Histogram
Box Plot
Scatter Plot
Heatmap
Area Chart
Pie/Donut where appropriate
```

The system should avoid generating meaningless charts.

---

# 33. Visualization Selection

Chart selection should depend on data type.

Examples:

```text
Date + Revenue            → Line Chart
Category + Revenue        → Bar Chart
Numeric + Numeric         → Scatter Plot
Numeric distribution      → Histogram
Category distribution     → Bar Chart
```

---

# 34. Correlation Analysis

For numerical variables, calculate appropriate correlation metrics.

Default:

```text
Pearson correlation
```

Where appropriate, use:

```text
Spearman correlation
```

The platform must clearly label correlation as association.

It must not automatically claim causation.

---

# 35. Outlier Detection

The system should identify potential outliers using appropriate methods.

Possible methods:

- IQR
- Z-score
- Domain thresholds

Outliers should initially be:

```text
Detected
Flagged
Explained
```

They should not automatically be deleted.

---

# 36. Retail Analytics

V1 should provide specialized retail/e-commerce analysis when the required fields are available.

---

# 37. Sales Analysis

Calculate:

```text
Total Revenue
Total Orders
Total Quantity
Average Order Value
Average Revenue per Customer
Revenue Growth
Order Growth
```

Where appropriate.

---

# 38. Customer Analysis

Calculate:

```text
Total Customers
New Customers
Returning Customers
Repeat Purchase Rate
Average Customer Revenue
Average Orders per Customer
```

Only calculate metrics when the necessary fields are available.

---

# 39. Customer Segmentation

The system should support rule-based customer segmentation.

Initial segments:

```text
High Value
Regular
Occasional
At Risk
```

Segmentation rules must be documented.

The system must not present segments as objective truths.

They are analytical classifications based on defined rules.

---

# 40. RFM Analysis

Where transaction dates and customer identifiers exist, calculate:

```text
Recency
Frequency
Monetary
```

Generate:

```text
RFM Score
Customer Segment
```

Example:

```text
Customer A

Recency: 12 days
Frequency: 14 orders
Monetary: ₹82,000

RFM Score: 555
```

---

# 41. Product Analysis

Where product information exists, calculate:

```text
Top Products
Bottom Products
Revenue by Product
Quantity by Product
Revenue by Category
Quantity by Category
Product Contribution
```

---

# 42. Discount Analysis

Where discount and revenue/margin data exist, analyze:

```text
Discount Level
Revenue
Orders
Average Order Value
Margin if available
```

The platform must distinguish association from causation.

---

# 43. Payment Analysis

Where payment method exists, calculate:

```text
Orders by Payment Method
Revenue by Payment Method
Average Order Value by Payment Method
```

---

# 44. Geographic Analysis

Where location data exists, calculate:

```text
Revenue by Country
Revenue by State
Revenue by City
Orders by Region
Customer distribution
```

---

# 45. Time-Based Analysis

Where a valid date exists, calculate:

```text
Daily Revenue
Weekly Revenue
Monthly Revenue
Yearly Revenue
Month-over-Month Growth
Year-over-Year Growth
```

Metrics should only be calculated where the required time period is meaningful.

---

# 46. SQL Analytics Engine

Clean analytical data must be available for SQL analysis.

The system must create an analytics representation suitable for SQL querying.

SQL analysis should cover:

```text
Sales
Customers
Products
Categories
Time
Geography
Loyalty
Purchase behavior
```

---

# 47. SQL Query Explorer

Users must be able to view generated SQL.

Example:

```sql
SELECT
    customer_id,
    SUM(revenue) AS total_revenue
FROM transactions
GROUP BY customer_id
ORDER BY total_revenue DESC;
```

The UI should display:

```text
Question
Generated SQL
Execution status
Result table
Execution time
```

---

# 48. SQL Safety

User-provided or AI-generated SQL must not have unrestricted access to production application tables.

Analytics queries must execute in a controlled/read-only analytical environment.

The following operations are not allowed through the analytics query interface:

```text
DROP
DELETE
UPDATE
INSERT
ALTER
TRUNCATE
```

---

# 49. Business Metrics

The analytics engine must produce structured metrics.

Example:

```json
{
  "metric_name": "total_revenue",
  "value": 8420000,
  "unit": "INR",
  "source": "sales_table",
  "calculation": "SUM(revenue)"
}
```

Metrics must be machine-readable.

---

# 50. Insight Generation

Insights must be generated from verified metrics.

An insight should contain:

```text
Title
Description
Evidence
Metric
Source
Supporting Query
Confidence
```

Example:

```text
Title:
High-value customers drive a large share of revenue.

Description:
High-value customers contribute 51.7% of total revenue
while representing 18% of customers.

Evidence:
Revenue contribution = 51.7%
Customer share = 18%

Source:
Customer segmentation SQL analysis.
```

---

# 51. Insight Rules

The system must never fabricate:

- Numbers
- Percentages
- Trends
- Customer counts
- Revenue
- Correlations

Every numerical statement must reference a verified metric.

---

# 52. Recommendation Engine

Recommendations should be based on observed evidence.

Example:

```text
Finding:
Repeat customers have a higher average order value.

Recommendation:
Investigate retention initiatives focused on existing
high-value customers.
```

Recommendations must be phrased as suggestions, not guaranteed outcomes.

---

# 53. AI Assistant

An optional AI layer may provide:

```text
Dataset explanation
Insight explanation
Natural-language summaries
SQL assistance
Report generation
Presentation generation
```

However:

> The AI must never replace the deterministic analytics engine.

---

# 54. Ask Your Data

Future/V1.5 capability.

Users may ask:

```text
Which product category generated the most revenue?

Why did revenue increase in Q3?

Which customer segment has the highest AOV?

What are the major data-quality problems?
```

The system should follow this flow:

```text
Question
 ↓
Intent
 ↓
Relevant data
 ↓
SQL / analytical calculation
 ↓
Execution
 ↓
Verified result
 ↓
Natural language response
```

---

# 55. Power BI Integration

V1 must generate a Power BI-ready analytical structure.

For retail data, the preferred model is a star schema.

Example:

```text
dim_customer
dim_product
dim_date
dim_location
dim_payment

        ↓

fact_sales
```

---

# 56. Power BI Measures

Where fields exist, generate measures such as:

```text
Total Revenue
Total Orders
Total Quantity
Total Customers
Average Order Value
Repeat Customer Rate
Revenue Growth
Revenue per Customer
```

---

# 57. Power BI Dashboard

The dashboard specification should include:

## Page 1 — Executive Overview

```text
Total Revenue
Orders
Customers
AOV

Revenue Trend
Revenue by Category
Customer Segments
```

## Page 2 — Customer Analytics

```text
Customer Count
RFM Segments
Repeat Purchase Rate
Customer Revenue
```

## Page 3 — Product Analytics

```text
Top Products
Bottom Products
Category Revenue
Quantity
```

## Page 4 — Purchase Behavior

```text
Discount
Payment Method
Order Size
Purchase Frequency
```

## Page 5 — Geography

```text
Country
State
City
Revenue
Customers
```

---

# 58. Reports

The system must support report generation.

Supported formats:

```text
PDF
DOCX
```

The report must contain:

```text
Cover Page
Executive Summary
Dataset Overview
Data Quality
Data Preparation
EDA
SQL Analysis
Customer Analysis
Product Analysis
Sales Analysis
Key Insights
Recommendations
Limitations
Appendix
```

---

# 59. Presentation

The system must generate a presentation.

Supported format:

```text
PPTX
```

Recommended structure:

```text
Slide 1:  Title
Slide 2:  Business Problem
Slide 3:  Dataset Overview
Slide 4:  Data Quality
Slide 5:  Sales Performance
Slide 6:  Customer Analysis
Slide 7:  Product Analysis
Slide 8:  Purchase Behavior
Slide 9:  Key Insights
Slide 10: Recommendations
Slide 11: Next Steps
```

---

# 60. Reports Must Be Evidence-Based

Generated reports must use verified analytical outputs.

The report generator must not independently calculate conflicting metrics.

There should be one source of truth:

```text
Analytics Engine
       ↓
Verified Metrics
       ↓
Reports
Power BI
Insights
Presentations
```

---

# 61. Analysis Status

Analysis jobs must expose status.

Possible states:

```text
QUEUED
UPLOADING
VALIDATING
PROFILING
CLEANING
TRANSFORMING
EDA
SQL_ANALYSIS
INSIGHT_GENERATION
POWERBI_PREPARATION
REPORT_GENERATION
PRESENTATION_GENERATION
COMPLETED
FAILED
```

---

# 62. Progress UI

Users must see processing progress.

Example:

```text
Analysis in Progress

✓ Dataset uploaded
✓ Dataset validated
✓ Data profiled
✓ Data cleaned
✓ EDA completed
⏳ SQL analysis
○ Insights
○ Power BI
○ Reports
```

---

# 63. Background Processing

Long-running analytics must NOT execute inside a normal synchronous HTTP request.

Architecture:

```text
FastAPI
   ↓
Redis
   ↓
Celery Worker
   ↓
Analytics Pipeline
```

The frontend should poll or subscribe to progress updates.

---

# 64. Error Handling

Every processing stage must support failure handling.

Example:

```text
SQL Analysis Failed

The dataset was successfully cleaned,
but SQL analysis could not be completed.

Reason:
Required customer identifier was not detected.

[ View Details ]
[ Retry ]
```

Errors must be understandable to users.

Technical stack traces should not be exposed directly.

---

# 65. Partial Analysis

If a dataset lacks certain fields, the system must continue where possible.

Example: the dataset has

```text
product
revenue
date
```

but no:

```text
customer_id
```

The system should still perform:

```text
Sales Analysis
Product Analysis
Time Analysis
```

but disable:

```text
Customer Segmentation
RFM
Loyalty Analysis
```

The UI should explain why.

---

# 66. Feature Availability

Features must have states:

```text
Available
Unavailable
Processing
Failed
```

Example:

```text
Customer Analysis

Unavailable

Reason:
No customer identifier was detected in this dataset.
```

---

# 67. Data Privacy

User-uploaded datasets are private by default.

Users must not be able to access another user's data.

Every data-access operation must enforce ownership.

---

# 68. File Storage

Original datasets and generated files should be stored in object storage.

Examples:

```text
raw/
cleaned/
reports/
presentations/
exports/
```

The database stores metadata and references, not large binary datasets.

---

# 69. Database Requirements

Primary database:

```text
PostgreSQL
```

Core entities:

```text
users
projects
datasets
dataset_versions
dataset_columns
analysis_runs
data_quality_reports
cleaning_operations
metrics
insights
recommendations
sql_queries
reports
presentations
jobs
```

Detailed schema is defined in:

```text
DATABASE.md
```

---

# 70. Frontend Requirements

Frontend stack:

```text
Next.js
TypeScript
Tailwind CSS
Reusable component system
```

The application must be:

- Responsive
- Accessible
- Fast
- Component-driven
- Type-safe

---

# 71. Frontend Pages

Required pages:

```text
/                              Landing Page
/login                         Login
/signup                        Signup
/dashboard                     Main Dashboard
/projects                      Project List
/projects/new                  Project Creation
/projects/[id]                 Project Overview
/projects/[id]/dataset         Dataset
/projects/[id]/quality         Data Quality
/projects/[id]/preparation     Data Preparation
/projects/[id]/eda             EDA
/projects/[id]/sql             SQL Analysis
/projects/[id]/customers       Customer Analytics
/projects/[id]/products        Product Analytics
/projects/[id]/insights        Insights
/projects/[id]/recommendations Recommendations
/projects/[id]/powerbi         Power BI
/projects/[id]/reports         Reports
/settings                      Settings
```

---

# 72. UI States

Every major screen must implement:

```text
Loading
Skeleton
Empty
Success
Error
Processing
Partial
Retry
```

No page should appear broken while data is loading.

---

# 73. Responsive Design

The primary target is desktop because analytics dashboards require screen space.

The application must still work on:

```text
Desktop
Laptop
Tablet
Mobile
```

On mobile, complex tables and dashboards may become horizontally scrollable.

---

# 74. Accessibility

The platform should support:

- Keyboard navigation
- Semantic HTML
- Accessible labels
- Sufficient contrast
- Focus states
- Screen-reader-friendly controls

---

# 75. Performance Requirements

Targets:

```text
Initial page load:
Fast enough for normal broadband usage

Dashboard:
No unnecessary full-page reloads

Large datasets:
Processed asynchronously

Charts:
Avoid rendering millions of points directly in browser
```

Large datasets should be aggregated before visualization.

---

# 76. Dataset Size Strategy

V1 should define a configurable maximum upload size.

The exact limit should be determined based on deployment resources.

The architecture must allow future scaling.

The system should not assume that every dataset can fit entirely into browser memory.

---

# 77. Caching

Redis may be used for:

```text
Job state
Progress
Frequently requested analytics
Temporary computation results
Session-related data where appropriate
```

Caching must not cause stale analytical results to appear after a dataset version changes.

---

# 78. Observability

The system should provide:

### Application logs

```text
Authentication
Uploads
Analysis jobs
Errors
Report generation
```

### Worker logs

```text
Job started
Stage started
Stage completed
Stage failed
Execution time
```

### Analytics logs

```text
Dataset version
Pipeline version
Metrics generated
SQL execution
```

---

# 79. Auditability

Important events should be recorded.

Examples:

```text
Dataset uploaded
Dataset version created
Cleaning operation performed
Analysis started
Analysis completed
Report generated
Report downloaded
```

---

# 80. Testing Requirements

The product must include:

## Unit Tests

For:

- Data cleaning
- Data profiling
- Metrics
- Segmentation
- RFM
- SQL generation
- Validation

## Integration Tests

For:

- API
- Database
- Worker
- Analytics pipeline

## End-to-End Tests

For:

```text
Login
→ Create Project
→ Upload Dataset
→ Process
→ View Analysis
→ Generate Report
```

---

# 81. Analytics Correctness

Analytics tests must use deterministic datasets with known expected results.

Example input:

```text
Customer A: ₹100
Customer A: ₹200
Customer B: ₹300
```

Expected:

```text
Total Revenue = ₹600
Customer A    = ₹300
Customer B    = ₹300
```

The test must fail if the calculation is wrong.

---

# 82. Security Requirements

The application must:

- Validate authentication
- Enforce authorization
- Protect user data
- Validate uploaded files
- Sanitize filenames
- Avoid SQL injection
- Avoid arbitrary SQL execution
- Protect secrets through environment variables
- Avoid exposing stack traces
- Apply appropriate rate limits
- Validate API payloads

---

# 83. Environment Variables

Secrets must never be committed.

Examples:

```text
DATABASE_URL
REDIS_URL
AUTH_SECRET
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
OBJECT_STORAGE_ENDPOINT
OBJECT_STORAGE_ACCESS_KEY
OBJECT_STORAGE_SECRET_KEY
LLM_API_KEY
```

Actual values must exist only in environment configuration.

---

# 84. Docker

The application should support containerized development.

Expected services:

```text
frontend
backend
worker
postgres
redis
```

Optional:

```text
object-storage
```

---

# 85. Development Architecture

Local development:

```text
Browser
   ↓
Next.js
   ↓
FastAPI
   ↓
PostgreSQL

FastAPI
   ↓
Redis
   ↓
Celery Worker
   ↓
Analytics Engine
```

---

# 86. Production Architecture

Production should separate:

```text
Frontend
Backend API
Worker
Database
Redis
Object Storage
```

The architecture must allow each service to scale independently.

---

# 87. API Design Principles

APIs must:

- Use consistent naming
- Use appropriate HTTP methods
- Validate requests
- Return predictable response schemas
- Return useful errors
- Use pagination where necessary
- Avoid returning unnecessary large payloads

---

# 88. API Versioning

API routes should support future versioning.

Preferred:

```text
/api/v1/...
```

---

# 89. Pagination

Use pagination for:

- Projects
- Datasets
- Insights
- SQL queries
- Reports
- Large result tables

Never return thousands of records unnecessarily.

---

# 90. Data Table Requirements

Large analytical tables must support:

- Pagination
- Sorting
- Filtering
- Column selection
- Search where appropriate

---

# 91. Chart Requirements

Charts must:

- Have clear titles
- Have axis labels
- Use appropriate scales
- Provide tooltips
- Handle missing data
- Avoid unnecessary decoration
- Avoid misleading visualizations

---

# 92. Business Insight Requirements

Each insight must answer:

```text
What happened?
Why is it potentially important?
What evidence supports it?
What could the stakeholder investigate or do next?
```

The system must avoid unsupported causal claims.

---

# 93. Recommendation Requirements

Recommendations should:

- Reference a finding
- Reference evidence
- Be actionable
- Be appropriately qualified
- Avoid guaranteed outcomes

Example:

```text
Finding:
High-value customers contribute a large share of revenue.

Recommendation:
Investigate retention initiatives for high-value customers.
```

---

# 94. Limitations Section

Every generated report should include a limitations section.

Potential limitations:

```text
Missing values
Limited sample size
Potential data-quality issues
Observational data
Correlation does not imply causation
Unavailable variables
Potential selection bias
```

The system should include only relevant limitations.

---

# 95. Reproducibility

Every analysis must record:

```text
Dataset version
Pipeline version
Analysis configuration
Cleaning operations
SQL queries
Metric definitions
Timestamp
```

---

# 96. Source of Truth

The analytical source of truth is:

```text
Cleaned Dataset
      ↓
Analytics Engine
      ↓
Verified Metrics
```

These metrics feed:

```text
SQL Results
Power BI
Insights
Recommendations
Reports
Presentations
```

No downstream component should independently invent conflicting numbers.

---

# 97. AI Source of Truth

AI is NOT a numerical source of truth.

Correct:

```text
Python
SQL
Statistics
       ↓
Verified Metrics
       ↓
AI Explanation
```

Incorrect:

```text
Dataset
 ↓
LLM guesses analysis
 ↓
Dashboard
```

---

# 98. Design Requirements

The product must feel like a professional analytical SaaS product.

Visual characteristics:

```text
Dark
Premium
Minimal
Technical
Data-focused
Professional
High information density
Clear hierarchy
```

Avoid:

```text
Generic AI gradients
Excessive neon
Excessive glassmorphism
Huge decorative text
Unnecessary animations
Random colors
Clutter
```

Detailed visual specifications are defined in:

```text
DESIGN.md
```

---

# 99. Navigation Model

Primary sidebar:

```text
Overview
Projects
Datasets
Analysis
Insights
Reports
Power BI
Settings
```

Within a project:

```text
Overview
Dataset
Quality
Preparation
EDA
SQL
Customers
Products
Insights
Recommendations
Power BI
Reports
```

---

# 100. Project Status

Projects can have:

```text
DRAFT
PROCESSING
COMPLETED
FAILED
ARCHIVED
```

---

# 101. Dataset Status

Datasets can have:

```text
UPLOADED
VALIDATING
VALID
INVALID
PROCESSING
READY
FAILED
```

---

# 102. Analysis Run Status

Analysis runs can have:

```text
QUEUED
RUNNING
COMPLETED
FAILED
CANCELLED
```

---

# 103. Retry Behavior

Failed processing jobs should be retryable where safe.

Retrying must not create inconsistent duplicate results.

Jobs should be idempotent where possible.

---

# 104. Idempotency

Important operations should be designed to avoid duplicate execution.

For example:

```text
Same dataset version
+
Same analysis configuration
```

should be identifiable as the same analysis run.

---

# 105. Notifications

The UI should notify the user when:

```text
Analysis completed
Report generated
Processing failed
Export completed
```

---

# 106. Search

Future-ready search should allow users to search:

```text
Projects
Datasets
Insights
Reports
```

---

# 107. Export

Users should be able to export:

```text
Cleaned dataset
Analysis results
SQL results
Reports
Presentations
Power BI-ready data/model
```

---

# 108. Project Deletion

Deleting a project should require confirmation.

The system must define whether deletion is:

```text
Soft delete
```

or

```text
Permanent deletion
```

Production implementation should prefer soft deletion where practical.

---

# 109. Dataset Deletion

Deleting a dataset should not silently delete unrelated project data.

Dependencies must be checked.

---

# 110. Data Retention

The system must define configurable retention policies for:

- Uploaded datasets
- Generated files
- Temporary files
- Failed jobs

---

# 111. Internationalization

V1:

```text
English only
```

Architecture should not make future localization impossible.

---

# 112. Currency

Retail analytics should not assume INR forever.

Currency should be represented as metadata.

Example:

```text
currency = INR
```

The display layer can format:

```text
₹84.2L
```

But the underlying metric should remain numeric.

---

# 113. Date Handling

Dates must be normalized internally.

The system should account for:

- Time zones
- Date formats
- Invalid dates
- Locale-specific formats

---

# 114. Numerical Precision

The analytics engine must preserve numerical precision internally.

Formatting should occur only at presentation time.

Example:

```text
Raw:     8420312.48392
Display: ₹84.20L
```

The underlying value remains `8420312.48392`.

---

# 115. Empty Dataset Handling

An empty dataset must be rejected.

Example:

```text
Dataset contains no usable rows.
Please upload a dataset containing data.
```

---

# 116. Unsupported Dataset Handling

If a dataset does not contain enough information for a particular analysis, the platform should explain the limitation.

Example:

```text
RFM Analysis unavailable.

Reason:
A transaction date and customer identifier are required.
```

---

# 117. Data Quality Transparency

Users must be able to inspect:

```text
What was wrong?
How many records were affected?
What was changed?
Why was it changed?
```

---

# 118. Data Lineage

The system should represent:

```text
Original Dataset
      ↓
Version 1
      ↓
Cleaning
      ↓
Version 2
      ↓
Transformation
      ↓
Version 3
      ↓
Analysis
```

---

# 119. Performance Goal

The platform should be optimized so that:

- UI interactions remain responsive.
- Long-running jobs execute asynchronously.
- Large datasets are not unnecessarily sent to the browser.
- Analytical results are cached where appropriate.
- Database queries are indexed appropriately.

Exact performance targets may be established during implementation.

---

# 120. Scalability

The architecture should allow:

```text
More users
More datasets
Larger datasets
More workers
More domains
More analytical modules
```

without requiring a complete rewrite.

---

# 121. Extensibility

Future domains may include:

```text
Marketing
Finance
HR
Banking
Education
Healthcare
Logistics
Subscription
Customer Support
```

The domain engine should therefore support:

```text
Domain
 ├── Semantic mappings
 ├── Metrics
 ├── SQL analysis
 ├── Visualizations
 ├── Insights
 └── Recommendations
```

---

# 122. Domain Plugin Architecture

Future domains should be implemented as independent analytical modules.

Example:

```text
domains/
├── retail/
├── marketing/
├── finance/
└── hr/
```

Each domain may define:

```text
required fields
optional fields
metrics
analysis modules
visualization rules
insight rules
```

---

# 123. V1 Retail Domain

The retail domain should support:

```text
Sales Analysis
Customer Analysis
Product Analysis
RFM
Loyalty
Discount Analysis
Payment Analysis
Geographic Analysis
Time-Series Analysis
```

---

# 124. Project Completion Definition

The project is considered complete only when:

```text
✓ User can register
✓ User can login
✓ User can authenticate with Google
✓ User can create a project
✓ User can upload supported datasets
✓ Dataset validation works
✓ Dataset preview works
✓ Profiling works
✓ Data quality works
✓ Cleaning works
✓ Dataset versioning works
✓ EDA works
✓ SQL analytics works
✓ Retail analytics works
✓ Customer segmentation works
✓ RFM works where possible
✓ Insights are evidence-backed
✓ Recommendations are generated
✓ Power BI model is generated
✓ Reports can be generated
✓ PPTX can be generated
✓ Background jobs work
✓ Errors are handled
✓ Authorization works
✓ Tests pass
✓ Production build works
```

---

# 125. Definition of Done

A feature is NOT complete merely because its UI exists.

A feature is complete only when:

```text
Frontend
+
Backend
+
Database
+
Validation
+
Error Handling
+
Tests
+
Documentation
```

are implemented where applicable.

---

# 126. Prohibited Shortcuts

The implementation must NOT:

- Hardcode analytics results
- Fake API responses
- Use static dashboard numbers in production
- Pretend an unfinished feature is complete
- Store secrets in source code
- Bypass authentication
- Bypass authorization
- Run unrestricted SQL
- Delete raw datasets during cleaning
- Make unsupported causal claims
- Invent insights
- Generate random charts just to fill the dashboard
- Add unnecessary dependencies
- Introduce architectural changes without documentation

---

# 127. Engineering Documentation

The following documents are authoritative:

```text
PRD.md
DESIGN.md
ARCHITECTURE.md
DATABASE.md
API_SPEC.md
ANALYTICS_SPEC.md
SQL_SPEC.md
POWERBI_SPEC.md
REPORTING_SPEC.md
AI_SPEC.md
SECURITY.md
TESTING.md
DEPLOYMENT.md
IMPLEMENTATION_PLAN.md
DECISIONS.md
```

If a conflict exists between documents, the conflict must be identified and resolved before implementation continues.

---

# 128. Priority System

Features are prioritized as follows.

## P0 — Critical

Required for core product functionality.

```text
Authentication
Project management
Dataset upload
Dataset validation
Profiling
Data quality
Cleaning
EDA
SQL analysis
Core retail analytics
```

## P1 — Important

```text
Insights
Recommendations
Power BI model
Reports
Presentation
```

## P2 — Enhancement

```text
AI assistant
Natural-language queries
Additional domains
Advanced segmentation
Collaboration
```

---

# 129. V1 Milestones

## Milestone 1 — Foundation

```text
Repository
Frontend
Backend
Database
Docker
Authentication
```

## Milestone 2 — Dataset

```text
Project
Upload
Validation
Preview
Metadata
```

## Milestone 3 — Analytics

```text
Profiling
Quality
Cleaning
EDA
```

## Milestone 4 — Business Analytics

```text
SQL
Sales
Customers
Products
RFM
Loyalty
```

## Milestone 5 — BI

```text
Power BI model
Dashboard
Metrics
```

## Milestone 6 — Reporting

```text
PDF
DOCX
PPTX
```

## Milestone 7 — Production

```text
Testing
Security
Observability
Deployment
Performance
```

---

# 130. Success Metrics

The product should be evaluated using the following.

## Functional Success

Percentage of core workflows completed successfully.

## Analytics Accuracy

Comparison between platform calculations and known expected results.

## Processing Reliability

Percentage of analysis jobs completed without failure.

## User Experience

Time required for a new user to:

```text
Login
→ Upload
→ Understand dataset
→ View first insight
```

## Reproducibility

Ability to reproduce results from the same dataset version and configuration.

---

# 131. Example End-to-End User Journey

A student signs into InsightForge.

They create:

```text
Retail Sales Analysis
```

They upload:

```text
retail_sales.csv
```

InsightForge reports:

```text
125,430 rows
18 columns
87/100 data quality
```

The system detects:

```text
Customer ID
Transaction ID
Product
Category
Revenue
Quantity
Discount
Purchase Date
```

The platform cleans the data. It removes:

```text
324 exact duplicates
```

and flags:

```text
421 missing age values
```

The system then performs EDA and discovers:

```text
Revenue trends
Category performance
Customer distribution
Purchase patterns
```

The SQL engine calculates:

```text
Revenue
Orders
AOV
Customer metrics
RFM
```

The platform generates:

```text
Key Insight:
High-value customers contribute a large share of total revenue.
```

The user can click:

```text
[ View Evidence ]
```

and see:

```text
Metric
SQL
Calculation
```

The Power BI model is generated. The user opens:

```text
Executive Dashboard
```

Finally:

```text
[ Generate PDF Report ]
[ Generate DOCX Report ]
[ Generate PPTX ]
```

The complete analytics project is now available.

---

# 132. Final Product Principle

InsightForge is not a chart generator.

It is not a generic AI chatbot.

It is not a CSV viewer.

It is not merely a Power BI dashboard.

It is an end-to-end analytics workflow:

```text
                    INSIGHTFORGE

Raw Data
   ↓
Data Preparation
   ↓
Data Quality
   ↓
Data Modeling
   ↓
Exploratory Analysis
   ↓
SQL Analysis
   ↓
Business Metrics
   ↓
Power BI
   ↓
Evidence
   ↓
Insights
   ↓
Recommendations
   ↓
Executive Report
   ↓
Presentation
```

The central principle is:

> **Every conclusion must be traceable back to the data and the analytical calculation that produced it.**

This principle must guide the entire implementation.
