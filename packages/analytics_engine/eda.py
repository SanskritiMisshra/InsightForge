"""
Stage 5: Exploratory Data Analysis (EDA) Engine
Generates descriptive statistics, frequency distributions, numeric histograms,
monthly trends, and Pearson correlation matrices with analytical disclaimers.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any
from .types import EDAResult, NumericHistogram, CategoryBreakdown, CorrelationItem


class EDAEngine:
    @classmethod
    def analyze(cls, df: pd.DataFrame) -> EDAResult:
        # 1. Summary Statistics for Numeric Columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        summary_stats: List[Dict[str, Any]] = []

        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) > 0:
                summary_stats.append({
                    "column": col,
                    "count": int(series.count()),
                    "mean": round(float(series.mean()), 2),
                    "std": round(float(series.std()), 2) if len(series) > 1 else 0.0,
                    "min": round(float(series.min()), 2),
                    "q25": round(float(series.quantile(0.25)), 2),
                    "median": round(float(series.median()), 2),
                    "q75": round(float(series.quantile(0.75)), 2),
                    "max": round(float(series.max()), 2),
                    "skewness": round(float(series.skew()), 2) if len(series) > 2 else 0.0,
                })

        # 2. Histograms for Key Numeric Columns
        histograms: List[NumericHistogram] = []
        for col in ["total_amount", "quantity", "unit_price", "discount_pct"]:
            if col in df.columns:
                series = df[col].dropna()
                if len(series) > 0:
                    counts, bin_edges = np.histogram(series, bins=10)
                    bins_list = []
                    for i in range(len(counts)):
                        bins_list.append({
                            "bin_start": round(float(bin_edges[i]), 2),
                            "bin_end": round(float(bin_edges[i + 1]), 2),
                            "count": int(counts[i]),
                        })
                    histograms.append(NumericHistogram(column_name=col, bins=bins_list))

        # 3. Category Breakdown & Revenue Contribution
        category_breakdowns: List[CategoryBreakdown] = []
        for cat_col in ["category", "payment_method", "region"]:
            if cat_col in df.columns:
                bd_list = []
                total_rows = len(df)
                total_rev = float(df["total_amount"].sum()) if "total_amount" in df.columns else 0.0

                grouped = df.groupby(cat_col)
                counts = grouped.size()
                revs = grouped["total_amount"].sum() if "total_amount" in df.columns else pd.Series(0, index=counts.index)

                for cat_val, count in counts.items():
                    rev = float(revs.get(cat_val, 0.0))
                    bd_list.append({
                        "category": str(cat_val),
                        "count": int(count),
                        "percentage": round((count / total_rows) * 100, 2) if total_rows > 0 else 0.0,
                        "revenue": round(rev, 2),
                        "revenue_pct": round((rev / total_rev) * 100, 2) if total_rev > 0 else 0.0,
                    })

                # Sort by revenue descending
                bd_list.sort(key=lambda x: x["revenue"], reverse=True)
                category_breakdowns.append(CategoryBreakdown(column_name=cat_col, breakdown=bd_list))

        # 4. Monthly Revenue Time Series
        monthly_revenue: List[Dict[str, Any]] = []
        for date_col in ["order_date", "date", "transaction_date"]:
            if date_col in df.columns and "total_amount" in df.columns:
                try:
                    df_temp = df.copy()
                    df_temp["_parsed_dt"] = pd.to_datetime(df_temp[date_col])
                    df_temp["_month_key"] = df_temp["_parsed_dt"].dt.strftime("%Y-%m")
                    m_grouped = df_temp.groupby("_month_key")
                    m_rev = m_grouped["total_amount"].sum()
                    m_orders = m_grouped["order_id"].nunique() if "order_id" in df.columns else m_grouped.size()

                    for month_key in sorted(m_rev.index):
                        rev_val = float(m_rev[month_key])
                        ord_count = int(m_orders[month_key])
                        aov = round(rev_val / ord_count, 2) if ord_count > 0 else 0.0
                        monthly_revenue.append({
                            "month": month_key,
                            "revenue": round(rev_val, 2),
                            "orders": ord_count,
                            "aov": aov,
                        })
                    break
                except Exception:
                    pass

        # 5. Pearson Correlation Matrix
        correlation_matrix: List[CorrelationItem] = []
        if len(numeric_cols) > 1:
            corr_df = df[numeric_cols].corr(method="pearson").round(3)
            for x_col in corr_df.columns:
                for y_col in corr_df.index:
                    val = float(corr_df.loc[y_col, x_col])
                    if not np.isnan(val):
                        correlation_matrix.append(
                            CorrelationItem(
                                x=str(x_col),
                                y=str(y_col),
                                correlation=val,
                            )
                        )

        return EDAResult(
            summary_stats=summary_stats,
            histograms=histograms,
            category_breakdowns=category_breakdowns,
            correlation_matrix=correlation_matrix,
            monthly_revenue=monthly_revenue,
        )
