"""
InsightForge Unified Backend Server
FastAPI server serving:
1. REST API endpoints for all 10 analytics pipeline stages (DuckDB, Quality, Cleaning, EDA, RFM, SQL Sandbox, Star Schema, Insights, Export)
2. Static web client assets (workspace.html, index.html, auth.html, factory.js) directly on port 8080.
"""

import os
import io
import time
from typing import Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response, PlainTextResponse
from pydantic import BaseModel

from packages.analytics_engine import AnalyticsPipeline
from packages.analytics_engine.pipeline import AnalyticsPipelineResult
from packages.analytics_engine.report_generator import ExecutiveReportGenerator
from packages.analytics_engine.powerbi_packager import PowerBIPackager
from packages.storage import init_db, DatabaseRepository, MetricPersister, get_db_connection

app = FastAPI(
    title="InsightForge Analytics Platform API",
    description="Deterministic, audit-traceable analytics and BI platform API.",
    version="1.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active pipeline instance cache
ACTIVE_PIPELINE: Optional[AnalyticsPipelineResult] = None


@app.on_event("startup")
def startup_event():
    global ACTIVE_PIPELINE
    init_db()
    print("[InsightForge] Multi-tenant SQLite database initialized in data/insightforge.db")
    print("[InsightForge] Initializing canonical benchmark retail dataset...")
    ACTIVE_PIPELINE = AnalyticsPipeline.run_benchmark(n_rows=10000)
    print(f"[InsightForge] Benchmark initialized: {ACTIVE_PIPELINE.metadata.row_count} rows, Quality: {ACTIVE_PIPELINE.quality_profile.overall_score}/100, Cleaned SHA: {ACTIVE_PIPELINE.cleaning_result.cleaned_sha256[:12]}...")
    try:
        saved_metrics = MetricPersister.persist_pipeline_metrics(ACTIVE_PIPELINE)
        print(f"[InsightForge] Canonical Metric Registry: {len(saved_metrics)} metrics persisted to database.")
    except Exception as e:
        print(f"[InsightForge] Metric persistence warning: {e}")


class SQLRequest(BaseModel):
    query: str


# ==========================================
# REST API Endpoints
# ==========================================

@app.get("/api/v1/health")
def get_health():
    return {
        "status": "healthy",
        "service": "InsightForge Core Analytics",
        "version": "1.0.0",
        "engine": "DuckDB 1.5.6 + Python 3.14 Vectorized",
        "dataset_loaded": ACTIVE_PIPELINE is not None,
    }


@app.get("/api/v1/pipeline/overview")
def get_overview():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")

    df = ACTIVE_PIPELINE.cleaned_df
    total_rev = float(df["total_amount"].sum()) if "total_amount" in df.columns else 0.0
    total_orders = int(df["order_id"].nunique()) if "order_id" in df.columns else len(df)
    total_cust = int(df["customer_id"].nunique()) if "customer_id" in df.columns else 0
    aov = round(total_rev / total_orders, 2) if total_orders > 0 else 0.0

    return {
        "metadata": ACTIVE_PIPELINE.metadata.model_dump(),
        "cleaning": {
            "version": ACTIVE_PIPELINE.cleaning_result.version,
            "cleaned_rows": ACTIVE_PIPELINE.cleaning_result.cleaned_rows,
            "dropped_duplicates": ACTIVE_PIPELINE.cleaning_result.dropped_duplicates,
            "cleaned_sha256": ACTIVE_PIPELINE.cleaning_result.cleaned_sha256,
        },
        "kpis": {
            "total_revenue": round(total_rev, 2),
            "total_orders": total_orders,
            "active_customers": total_cust,
            "average_order_value": aov,
            "quality_score": ACTIVE_PIPELINE.quality_profile.overall_score,
        },
        "quality_score": ACTIVE_PIPELINE.quality_profile.overall_score,
        "monthly_trend": ACTIVE_PIPELINE.eda_result.monthly_revenue,
        "top_insights": [i.model_dump() for i in ACTIVE_PIPELINE.insights[:3]],
    }


@app.get("/api/v1/datasets/active/quality")
def get_quality():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    return ACTIVE_PIPELINE.quality_profile.model_dump()


@app.get("/api/v1/datasets/active/cleaning-log")
def get_cleaning_log():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    return ACTIVE_PIPELINE.cleaning_result.model_dump()


@app.get("/api/v1/datasets/active/schema")
def get_schema():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    return [c.model_dump() for c in ACTIVE_PIPELINE.columns]


@app.get("/api/v1/datasets/active/eda")
def get_eda():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    return ACTIVE_PIPELINE.eda_result.model_dump()


@app.get("/api/v1/datasets/active/rfm")
def get_rfm():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    return ACTIVE_PIPELINE.rfm_result.model_dump()


@app.get("/api/v1/datasets/active/products")
def get_products():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    return ACTIVE_PIPELINE.product_result.model_dump()


@app.post("/api/v1/datasets/active/sql")
def execute_sql(req: SQLRequest):
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    try:
        res = ACTIVE_PIPELINE.execute_sql(req.query)
        return res.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DuckDB Execution Error: {str(e)}")


@app.get("/api/v1/datasets/active/star-schema")
def get_star_schema():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    return ACTIVE_PIPELINE.star_schema.model_dump()


@app.get("/api/v1/datasets/active/insights")
def get_insights():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    return [i.model_dump() for i in ACTIVE_PIPELINE.insights]


@app.get("/api/v1/datasets/active/evidence/{metric_key}")
def get_evidence(metric_key: str):
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    return ACTIVE_PIPELINE.get_evidence(metric_key).model_dump()


@app.post("/api/v1/datasets/upload")
async def upload_dataset(file: UploadFile = File(...)):
    global ACTIVE_PIPELINE
    content = await file.read()
    filename = file.filename or "uploaded_data.csv"
    try:
        new_pipeline = AnalyticsPipeline.run_on_bytes(content, filename=filename, dataset_id="ds-custom")
        ACTIVE_PIPELINE = new_pipeline
        return {
            "message": "Dataset uploaded and processed through 10-stage pipeline successfully.",
            "metadata": ACTIVE_PIPELINE.metadata.model_dump(),
            "quality_score": ACTIVE_PIPELINE.quality_profile.overall_score,
            "cleaned_rows": ACTIVE_PIPELINE.cleaning_result.cleaned_rows,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Pipeline processing failed: {str(e)}")


@app.get("/api/v1/export/pbi-model")
def export_pbi_model():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")

    star_schema = ACTIVE_PIPELINE.star_schema
    # Export Power BI Model Definition JSON
    pbi_export = {
        "name": "InsightForge_Retail_StarSchema",
        "compatibilityLevel": 1550,
        "model": {
            "culture": "en-US",
            "tables": [t.model_dump() for t in star_schema.tables],
            "relationships": star_schema.relationships,
            "measures": [m.model_dump() for m in star_schema.dax_measures],
        },
    }
    return JSONResponse(
        content=pbi_export,
        headers={"Content-Disposition": 'attachment; filename="InsightForge_StarSchema_Model.json"'},
    )


@app.get("/api/v1/export/powerbi-zip")
def export_powerbi_zip():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    zip_bytes = PowerBIPackager.create_package(
        ACTIVE_PIPELINE.cleaned_df,
        ACTIVE_PIPELINE.cleaning_result.cleaned_sha256,
    )
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="InsightForge_PowerBI_Package.zip"'},
    )


@app.get("/api/v1/export/report-pdf")
def export_report_pdf():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    pdf_bytes = ExecutiveReportGenerator.generate_pdf(ACTIVE_PIPELINE)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="InsightForge_Executive_Brief.pdf"'},
    )


@app.get("/api/v1/export/report-docx")
def export_report_docx():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    docx_bytes = ExecutiveReportGenerator.generate_docx(ACTIVE_PIPELINE)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="InsightForge_Executive_Brief.docx"'},
    )


@app.get("/api/v1/export/report-pptx")
def export_report_pptx():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")
    pptx_bytes = ExecutiveReportGenerator.generate_pptx(ACTIVE_PIPELINE)
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": 'attachment; filename="InsightForge_Executive_Deck.pptx"'},
    )


@app.get("/api/v1/projects")
def get_projects():
    proj = DatabaseRepository.get_default_project()
    return [proj] if proj else []


@app.get("/api/v1/metrics")
def get_metrics():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM metrics ORDER BY created_at DESC LIMIT 50")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/v1/export/report-markdown")
def export_report_markdown():
    if not ACTIVE_PIPELINE:
        raise HTTPException(status_code=503, detail="Analytics pipeline initializing")

    df = ACTIVE_PIPELINE.cleaned_df
    total_rev = float(df["total_amount"].sum()) if "total_amount" in df.columns else 0.0
    total_orders = int(df["order_id"].nunique()) if "order_id" in df.columns else len(df)
    total_cust = int(df["customer_id"].nunique()) if "customer_id" in df.columns else 0
    aov = round(total_rev / total_orders, 2) if total_orders > 0 else 0.0

    md_content = f"""# InsightForge Automated Analytics & BI Platform
## Executive Analytics Brief & Audit Lineage Report

**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  
**Dataset Version:** {ACTIVE_PIPELINE.cleaning_result.version} · Cleaned  
**Cryptographic Lineage SHA-256:** `{ACTIVE_PIPELINE.cleaning_result.cleaned_sha256}`  
**Data Quality Score:** {ACTIVE_PIPELINE.quality_profile.overall_score}/100  

---

### 1. Executive Summary KPIs

| Metric | Formatted Value | Deterministic Formula | Verification Query |
| :--- | :--- | :--- | :--- |
| **Total Revenue** | ₹{total_rev:,.2f} | `SUM(total_amount)` | `SELECT ROUND(SUM(total_amount), 2) FROM transactions;` |
| **Total Orders** | {total_orders:,} | `DISTINCTCOUNT(order_id)` | `SELECT COUNT(DISTINCT order_id) FROM transactions;` |
| **Active Customers** | {total_cust:,} | `DISTINCTCOUNT(customer_id)` | `SELECT COUNT(DISTINCT customer_id) FROM transactions;` |
| **Average Order Value** | ₹{aov:,.2f} | `Total Revenue / Total Orders` | `SELECT ROUND(SUM(total_amount)/COUNT(DISTINCT order_id), 2) FROM transactions;` |

---

### 2. Data Quality Audit & Cleaning Trail
- **Original Ingested Rows:** {ACTIVE_PIPELINE.cleaning_result.original_rows:,}
- **Cleaned Dataset Rows:** {ACTIVE_PIPELINE.cleaning_result.cleaned_rows:,}
- **Exact Duplicate Rows Removed:** {ACTIVE_PIPELINE.cleaning_result.dropped_duplicates:,}
- **Missing Value Imputations:** {ACTIVE_PIPELINE.cleaning_result.imputed_cells:,}

#### Cleaning Operations Executed:
"""
    for entry in ACTIVE_PIPELINE.cleaning_result.audit_log:
        md_content += f"- **Step {entry.step_number} [{entry.operation}]:** {entry.description} *(Justification: {entry.justification})*\n"

    md_content += """
---

### 3. Customer RFM Segmentation Analysis

| Segment | Code | Customers | % Base | Revenue | % Revenue | AOV | Avg Recency |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    for seg in ACTIVE_PIPELINE.rfm_result.segments:
        md_content += f"| **{seg.name}** | `{seg.code}` | {seg.customer_count:,} | {seg.customer_pct}% | ₹{seg.total_revenue:,.2f} | {seg.revenue_pct}% | ₹{seg.avg_order_value:,.2f} | {seg.avg_recency_days:.0f} days |\n"

    md_content += """
---

### 4. Deterministic Insights & Evidence Findings
"""
    for ins in ACTIVE_PIPELINE.insights:
        md_content += f"""
#### [{ins.id}] {ins.title} (Severity: {ins.severity})
- **Finding:** {ins.finding}
- **Business Impact:** {ins.business_impact}
- **Actionable Recommendation:** {ins.actionable_recommendation}
- **Confidence:** {int(ins.confidence * 100)}% (Deterministic Python/SQL Aggregation)
- **Metric References:** {', '.join(ins.metric_refs)}
"""

    md_content += """
---

### 5. Analytical Limitations & Governance
- **Methodology:** All calculations are deterministic. Zero predictive extrapolation has been fabricated.
- **Correlation Disclaimer:** Pearson correlation indicates mathematical linear association; it does not establish causal dependency.
- **Lineage Verification:** Every metric in this report maps directly to immutable dataset hash `{ACTIVE_PIPELINE.cleaning_result.cleaned_sha256}`.
"""

    return PlainTextResponse(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": 'attachment; filename="InsightForge_Executive_Brief.md"'},
    )


# ==========================================
# Static Files & UI Mounting
# ==========================================
# Mount workspace directory so http://localhost:8080/ serves index.html, workspace.html, auth.html, factory.js
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    # Run strictly on port 8080
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=False)
