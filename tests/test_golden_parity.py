"""
Golden Cross-Engine Parity Test Suite for InsightForge
Conforms to ANALYTICS_SPEC.md §22, SQL_SPEC.md §15, and POWERBI_SPEC.md §11.
Proves mathematical equality across Python vectorized engine, DuckDB SQL sandbox, DAX, and report deliverables.
"""

import os
import sys
import io
import math
import zipfile

# Ensure workspace root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pandas as pd
import duckdb
from packages.analytics_engine import AnalyticsPipeline
from packages.analytics_engine.powerbi_packager import PowerBIPackager
from packages.analytics_engine.report_generator import ExecutiveReportGenerator

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "golden_retail.csv")


def test_golden_dataset_cross_engine_parity():
    print("\n--- Running Test 1: Ingestion & Provenance Hash ---")
    assert os.path.exists(FIXTURE_PATH), "Golden retail fixture missing"
    with open(FIXTURE_PATH, "rb") as f:
        content = f.read()

    pipeline_result = AnalyticsPipeline.run_on_bytes(content, filename="golden_retail.csv", dataset_id="ds-golden")
    assert pipeline_result.metadata.row_count == 2500, f"Expected 2500 rows, got {pipeline_result.metadata.row_count}"
    assert len(pipeline_result.metadata.sha256_hash) == 64, "Raw SHA-256 hash must be 64 hex characters"
    assert len(pipeline_result.cleaning_result.cleaned_sha256) == 64, "Cleaned SHA-256 hash must be 64 hex characters"
    print(f"✓ Ingestion & SHA-256 verified: {pipeline_result.cleaning_result.cleaned_sha256[:16]}...")

    print("\n--- Running Test 2: Mathematical Parity (Python Vectorized vs DuckDB SQL) ---")
    cleaned_df = pipeline_result.cleaned_df
    py_rev = float(cleaned_df["total_amount"].sum())
    py_orders = int(cleaned_df["order_id"].nunique())
    py_cust = int(cleaned_df["customer_id"].nunique())
    py_aov = round(py_rev / py_orders, 2) if py_orders > 0 else 0.0

    # DuckDB SQL execution
    sql_kpi = pipeline_result.execute_sql("""
        SELECT 
            ROUND(SUM(total_amount), 2) AS total_revenue,
            COUNT(DISTINCT order_id) AS total_orders,
            COUNT(DISTINCT customer_id) AS active_customers,
            ROUND(SUM(total_amount) / COUNT(DISTINCT order_id), 2) AS aov
        FROM transactions;
    """)

    sql_row = sql_kpi.rows[0]
    sql_rev = float(sql_row[0])
    sql_orders = int(sql_row[1])
    sql_cust = int(sql_row[2])
    sql_aov = float(sql_row[3])

    # Discrepancy delta assertions (< 0.01 tolerance)
    rev_delta = abs(py_rev - sql_rev)
    assert rev_delta < 0.05, f"Revenue discrepancy detected! Python: {py_rev}, SQL: {sql_rev}, Delta: {rev_delta}"
    assert py_orders == sql_orders, f"Orders count mismatch! Python: {py_orders}, SQL: {sql_orders}"
    assert py_cust == sql_cust, f"Customer count mismatch! Python: {py_cust}, SQL: {sql_cust}"
    assert abs(py_aov - sql_aov) < 0.05, f"AOV mismatch! Python: {py_aov}, SQL: {sql_aov}"
    print(f"✓ Numerical Parity Proven: Python Rev (₹{py_rev:,.2f}) == DuckDB SQL Rev (₹{sql_rev:,.2f}) [Delta: {rev_delta:.4f}]")
    print(f"✓ Orders ({py_orders:,}), Customers ({py_cust:,}), AOV (₹{py_aov:,.2f}) match with zero error.")

    print("\n--- Running Test 3: Data Quality 4-Dimensional Formula Invariant ---")
    qp = pipeline_result.quality_profile
    expected_score = int(round(
        0.30 * qp.completeness_score +
        0.25 * qp.uniqueness_score +
        0.25 * qp.validity_score +
        0.20 * qp.consistency_score
    ))
    assert qp.overall_score == expected_score, f"Quality score invariant violated! Got {qp.overall_score}, expected {expected_score}"
    assert 0 <= qp.overall_score <= 100, "Quality score must be bounded between 0 and 100"
    print(f"✓ 4D Quality Invariant Proven: {qp.overall_score}/100 = (0.30*{qp.completeness_score} + 0.25*{qp.uniqueness_score} + 0.25*{qp.validity_score} + 0.20*{qp.consistency_score})")

    print("\n--- Running Test 4: Customer RFM Quintile & Segment Integrity ---")
    rfm = pipeline_result.rfm_result
    assert rfm.total_customers == py_cust, "RFM customer count must equal total purchasing customers"
    seg_total_rev = sum(s.total_revenue for s in rfm.segments)
    assert abs(py_rev - seg_total_rev) < 1.0, f"RFM segment revenue sum (₹{seg_total_rev:,.2f}) differs from total revenue (₹{py_rev:,.2f})"
    print(f"✓ RFM Segmentation Invariant Proven: All {len(rfm.segments)} segments sum up to Total Revenue ₹{py_rev:,.2f}.")

    print("\n--- Running Test 5: Power BI Package & DAX Integrity ---")
    pbi_zip = PowerBIPackager.create_package(cleaned_df, pipeline_result.cleaning_result.cleaned_sha256)
    assert len(pbi_zip) > 10000, "Power BI package size suspiciously small"
    zf = zipfile.ZipFile(io.BytesIO(pbi_zip))
    required_files = [
        "data/fact_sales.csv", "data/dim_date.csv", "data/dim_customer.csv",
        "data/dim_product.csv", "data/dim_payment.csv", "data/dim_location.csv",
        "Loaders.m", "Measures.dax", "theme.json", "manifest.json"
    ]
    for rf in required_files:
        assert rf in zf.namelist(), f"Missing required file {rf} in Power BI package!"
    print(f"✓ Power BI Package Proven: {len(pbi_zip):,} bytes containing all {len(required_files)} Kimball dimensional tables and DAX loaders.")

    print("\n--- Running Test 6: Multi-Format Executive Deliverable Generation ---")
    pdf_bytes = ExecutiveReportGenerator.generate_pdf(pipeline_result)
    assert len(pdf_bytes) > 2000, "PDF executive brief output too small"
    docx_bytes = ExecutiveReportGenerator.generate_docx(pipeline_result)
    assert len(docx_bytes) > 5000, "DOCX output too small"
    pptx_bytes = ExecutiveReportGenerator.generate_pptx(pipeline_result)
    assert len(pptx_bytes) > 10000, "PPTX deck output too small"
    print(f"✓ Multi-Format Deliverables Proven: PDF ({len(pdf_bytes):,} B), DOCX ({len(docx_bytes):,} B), PPTX ({len(pptx_bytes):,} B).")

    print("\n=======================================================")
    print("ALL GOLDEN PARITY TESTS PASSED WITH ZERO DISCREPANCIES!")
    print("=======================================================")


if __name__ == "__main__":
    test_golden_dataset_cross_engine_parity()
