"""
Stage 6: Customer RFM Segmentation Engine
Calculates Recency, Frequency, Monetary quintiles (1-5) and segments customers into:
- High Value (Champions / Loyal)
- Regular (Steady / Active)
- Occasional (New / Low Frequency)
- At Risk (Churn Risk / Inactive)
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any
from .types import RFMAnalysisResult, RFMSegmentSummary


class RFMEngine:
    @classmethod
    def analyze(cls, df: pd.DataFrame) -> RFMAnalysisResult:
        # Find customer, date, order, and amount columns
        cust_col = next((c for c in ["customer_id", "user_id", "client_id"] if c in df.columns), None)
        date_col = next((c for c in ["order_date", "date", "transaction_date"] if c in df.columns), None)
        order_col = next((c for c in ["order_id", "invoice_no"] if c in df.columns), None)
        amount_col = next((c for c in ["total_amount", "revenue", "amount", "sales"] if c in df.columns), None)

        if not (cust_col and date_col and amount_col):
            # Fallback empty result
            return RFMAnalysisResult(
                reference_date=datetime.utcnow().strftime("%Y-%m-%d"),
                total_customers=0,
                segments=[],
                grid_5x5=[],
                rules_disclaimer="Insufficient customer transaction columns to compute RFM.",
            )

        df_rfm = df.copy()
        df_rfm["_dt"] = pd.to_datetime(df_rfm[date_col])
        ref_date = df_rfm["_dt"].max() + pd.Timedelta(days=1)

        # Aggregate per customer
        cust_group = df_rfm.groupby(cust_col)
        recency = cust_group["_dt"].apply(lambda s: (ref_date - s.max()).days)
        frequency = cust_group[order_col].nunique() if order_col else cust_group.size()
        monetary = cust_group[amount_col].sum()

        cust_df = pd.DataFrame({
            "recency": recency,
            "frequency": frequency,
            "monetary": monetary,
        })

        total_customers = len(cust_df)
        total_rev = float(cust_df["monetary"].sum())

        # Quintile scoring (1 to 5)
        # For Recency: lower days is better, so rank(ascending=False) gives higher score for lower recency
        cust_df["r_score"] = pd.qcut(cust_df["recency"].rank(method="first", ascending=False), 5, labels=[1, 2, 3, 4, 5]).astype(int)
        cust_df["f_score"] = pd.qcut(cust_df["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
        cust_df["m_score"] = pd.qcut(cust_df["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)

        # Segment Assignment Logic
        def assign_segment(row) -> str:
            r, f = row["r_score"], row["f_score"]
            if r >= 4 and f >= 4:
                return "High Value"
            elif r <= 2:
                return "At Risk"
            elif r >= 4 and f <= 2:
                return "Occasional"
            else:
                return "Regular"

        cust_df["segment"] = cust_df.apply(assign_segment, axis=1)

        # Define segment metadata
        seg_meta = {
            "High Value": {
                "code": "HV",
                "color": "#10B981",  # Emerald
                "desc": "Top spending and most frequent recent buyers. Highest customer lifetime value.",
            },
            "Regular": {
                "code": "REG",
                "color": "#3B82F6",  # Blue
                "desc": "Active customers with steady purchase cadence and moderate order sizes.",
            },
            "Occasional": {
                "code": "OCC",
                "color": "#F59E0B",  # Amber
                "desc": "Recent first-time or single-purchase shoppers. Prime targets for repeat conversion.",
            },
            "At Risk": {
                "code": "AR",
                "color": "#EF4444",  # Crimson
                "desc": "Previously active customers with no transactions in 90+ days. Churn intervention required.",
            },
        }

        segments: List[RFMSegmentSummary] = []
        for seg_name in ["High Value", "Regular", "Occasional", "At Risk"]:
            sub = cust_df[cust_df["segment"] == seg_name]
            count = len(sub)
            rev = float(sub["monetary"].sum())
            cust_pct = round((count / total_customers) * 100, 2) if total_customers > 0 else 0.0
            rev_pct = round((rev / total_rev) * 100, 2) if total_rev > 0 else 0.0
            aov = round(rev / float(sub["frequency"].sum()), 2) if sub["frequency"].sum() > 0 else 0.0
            avg_rec = round(float(sub["recency"].mean()), 1) if count > 0 else 0.0
            avg_freq = round(float(sub["frequency"].mean()), 1) if count > 0 else 0.0

            segments.append(
                RFMSegmentSummary(
                    name=seg_name,
                    code=seg_meta[seg_name]["code"],
                    customer_count=count,
                    customer_pct=cust_pct,
                    total_revenue=round(rev, 2),
                    revenue_pct=rev_pct,
                    avg_order_value=aov,
                    avg_recency_days=avg_rec,
                    avg_frequency=avg_freq,
                    color=seg_meta[seg_name]["color"],
                    description=seg_meta[seg_name]["desc"],
                )
            )

        # Build 5x5 RFM Grid (Recency rows 1-5, Frequency columns 1-5)
        grid_5x5: List[List[Dict[str, Any]]] = []
        for r in range(5, 0, -1):  # R5 down to R1
            row_cells = []
            for f in range(1, 6):   # F1 up to F5
                sub_rf = cust_df[(cust_df["r_score"] == r) & (cust_df["f_score"] == f)]
                c_count = len(sub_rf)
                c_rev = float(sub_rf["monetary"].sum())
                row_cells.append({
                    "r": r,
                    "f": f,
                    "count": c_count,
                    "revenue": round(c_rev, 2),
                    "percentage": round((c_count / total_customers) * 100, 2) if total_customers > 0 else 0.0,
                })
            grid_5x5.append(row_cells)

        rules_disclaimer = (
            "Analytical Rules: R, F, and M scores (1-5) are computed using exact quintiles. "
            "Segments are assigned deterministically: High Value (R>=4, F>=4), At Risk (R<=2), "
            "Occasional (R>=4, F<=2), Regular (all remaining active buyers). No subjective labeling."
        )

        return RFMAnalysisResult(
            reference_date=ref_date.strftime("%Y-%m-%d"),
            total_customers=total_customers,
            segments=segments,
            grid_5x5=grid_5x5,
            rules_disclaimer=rules_disclaimer,
        )
