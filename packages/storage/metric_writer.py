"""
Metric Persister for InsightForge Canonical Metric Registry
Conforms to DATABASE.md §6.8 and ANALYTICS_SPEC.md §15.
Writes computed metrics to the append-only `metrics` table with cryptographic provenance.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from .db import get_db_connection


class MetricPersister:
    @classmethod
    def persist_pipeline_metrics(
        cls,
        pipeline_result,
        run_id: str = "run-default",
        dataset_version_id: str = "dsv-v2-cleaned",
    ) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cur = conn.cursor()

        df = pipeline_result.cleaned_df
        total_rev = float(df["total_amount"].sum()) if "total_amount" in df.columns else 0.0
        total_orders = int(df["order_id"].nunique()) if "order_id" in df.columns else len(df)
        total_cust = int(df["customer_id"].nunique()) if "customer_id" in df.columns else 0
        aov = round(total_rev / total_orders, 2) if total_orders > 0 else 0.0

        sha256_hash = pipeline_result.cleaning_result.cleaned_sha256
        now = datetime.utcnow().isoformat() + "Z"
        dataset_id = "ds-benchmark-retail"

        # Ensure project exists
        cur.execute("SELECT id FROM projects LIMIT 1")
        p_row = cur.fetchone()
        project_id = p_row[0] if p_row else "proj-0192a001-0000-7000-8000-000000000004"

        # Ensure dataset exists
        cur.execute("SELECT id FROM datasets WHERE id = ?", (dataset_id,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO datasets (id, project_id, name, original_filename, created_at) VALUES (?, ?, ?, ?, ?)",
                (dataset_id, project_id, pipeline_result.metadata.name, pipeline_result.metadata.name, now)
            )

        # Ensure dataset_version exists
        cur.execute("SELECT id FROM dataset_versions WHERE id = ?", (dataset_version_id,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO dataset_versions (
                    id, dataset_id, version_number, version_label, sha256_hash,
                    row_count, column_count, file_size_bytes, storage_path, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dataset_version_id, dataset_id, 2, "v2 · Cleaned", sha256_hash,
                pipeline_result.cleaning_result.cleaned_rows, len(pipeline_result.columns),
                pipeline_result.metadata.file_size_bytes, "data/clean.parquet", 1, now
            ))

        # Ensure analysis_run exists
        cur.execute("SELECT id FROM analysis_runs WHERE id = ?", (run_id,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO analysis_runs (
                    id, dataset_version_id, status, stage, progress_pct, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, dataset_version_id, "COMPLETED", "REPORT_READY", 100, now))

        metrics_to_save = [
            {
                "key": "total_revenue",
                "name": "Total Revenue",
                "category": "REVENUE",
                "formatted": f"₹{total_rev:,.2f}",
                "numeric": total_rev,
                "unit": "INR",
                "grain": "TOTAL",
                "formula": "SUM(total_amount) WHERE status != 'CANCELLED'",
                "sql": "SELECT ROUND(SUM(total_amount), 2) FROM transactions;",
            },
            {
                "key": "total_orders",
                "name": "Total Orders",
                "category": "VOLUME",
                "formatted": f"{total_orders:,}",
                "numeric": float(total_orders),
                "unit": "COUNT",
                "grain": "TOTAL",
                "formula": "COUNT(DISTINCT order_id)",
                "sql": "SELECT COUNT(DISTINCT order_id) FROM transactions;",
            },
            {
                "key": "active_customers",
                "name": "Active Customers",
                "category": "CUSTOMER",
                "formatted": f"{total_cust:,}",
                "numeric": float(total_cust),
                "unit": "COUNT",
                "grain": "TOTAL",
                "formula": "COUNT(DISTINCT customer_id)",
                "sql": "SELECT COUNT(DISTINCT customer_id) FROM transactions;",
            },
            {
                "key": "average_order_value",
                "name": "Average Order Value",
                "category": "EFFICIENCY",
                "formatted": f"₹{aov:,.2f}",
                "numeric": aov,
                "unit": "INR",
                "grain": "TRANSACTION",
                "formula": "Total Revenue / Total Orders",
                "sql": "SELECT ROUND(SUM(total_amount)/COUNT(DISTINCT order_id), 2) FROM transactions;",
            },
            {
                "key": "quality_score",
                "name": "Data Quality Score",
                "category": "QUALITY",
                "formatted": f"{pipeline_result.quality_profile.overall_score}/100",
                "numeric": float(pipeline_result.quality_profile.overall_score),
                "unit": "SCORE",
                "grain": "DATASET",
                "formula": "round(0.30*Completeness + 0.25*Uniqueness + 0.25*Validity + 0.20*Consistency)",
                "sql": "N/A (Multi-Dimensional Quality Evaluation)",
            },
        ]

        # Add RFM Segment Metrics
        for seg in pipeline_result.rfm_result.segments:
            metrics_to_save.append({
                "key": f"rfm_rev_{seg.code.lower()}",
                "name": f"{seg.name} Segment Revenue",
                "category": "SEGMENT",
                "formatted": f"₹{seg.total_revenue:,.2f}",
                "numeric": seg.total_revenue,
                "unit": "INR",
                "grain": "COHORT",
                "formula": f"SUM(total_amount) FOR {seg.name} cohort",
                "sql": f"SELECT SUM(revenue) FROM transactions WHERE segment = '{seg.name}';",
            })

        saved_records = []
        for m in metrics_to_save:
            metric_id = f"met-{uuid.uuid4()}"
            cur.execute("""
                INSERT INTO metrics (
                    id, run_id, dataset_version_id, metric_key, metric_name, category,
                    formatted_value, numeric_value, unit, grain, formula, underlying_sql, sha256_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric_id, run_id, dataset_version_id, m["key"], m["name"], m["category"],
                m["formatted"], m["numeric"], m["unit"], m["grain"], m["formula"], m["sql"],
                sha256_hash, now
            ))
            m["id"] = metric_id
            saved_records.append(m)

        conn.commit()
        conn.close()
        return saved_records

    @classmethod
    def get_metric_by_key(cls, metric_key: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM metrics WHERE metric_key = ? ORDER BY created_at DESC LIMIT 1", (metric_key,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
