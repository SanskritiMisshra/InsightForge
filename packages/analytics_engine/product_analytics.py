"""
Stage 7: Product & Payment Analytics Engine
Computes SKU performance, Pareto 80/20 revenue concentration, and payment method share.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any
from .types import ProductAnalyticsResult, ProductMetric, PaymentMethodDistribution


class ProductAnalyticsEngine:
    @classmethod
    def analyze(cls, df: pd.DataFrame) -> ProductAnalyticsResult:
        total_rev = float(df["total_amount"].sum()) if "total_amount" in df.columns else 0.0

        # 1. Product / SKU Metrics
        top_products: List[ProductMetric] = []
        if "product_id" in df.columns:
            prod_group = df.groupby(["product_id", "product_name", "category"])
            p_rev = prod_group["total_amount"].sum().reset_index()
            p_qty = prod_group["quantity"].sum().reset_index()

            merged = pd.merge(p_rev, p_qty, on=["product_id", "product_name", "category"])
            merged = merged.sort_values(by="total_amount", ascending=False).reset_index(drop=True)

            merged["rev_pct"] = (merged["total_amount"] / total_rev * 100).round(2)
            merged["cum_rev_pct"] = merged["rev_pct"].cumsum().round(2)

            for _, r in merged.iterrows():
                top_products.append(
                    ProductMetric(
                        sku=str(r["product_id"]),
                        product_name=str(r["product_name"]),
                        category=str(r["category"]),
                        units_sold=int(r["quantity"]),
                        revenue=round(float(r["total_amount"]), 2),
                        revenue_pct=float(r["rev_pct"]),
                        cumulative_revenue_pct=float(r["cum_rev_pct"]),
                        is_pareto_top_80=bool(r["cum_rev_pct"] <= 80.0),
                    )
                )

        # 2. Payment Method Distribution
        payment_distribution: List[PaymentMethodDistribution] = []
        if "payment_method" in df.columns:
            pay_group = df.groupby("payment_method")
            pay_counts = pay_group.size()
            pay_revs = pay_group["total_amount"].sum()

            for pm, count in pay_counts.items():
                rev = float(pay_revs.get(pm, 0.0))
                payment_distribution.append(
                    PaymentMethodDistribution(
                        payment_method=str(pm),
                        transaction_count=int(count),
                        total_revenue=round(rev, 2),
                        revenue_pct=round((rev / total_rev) * 100, 2) if total_rev > 0 else 0.0,
                    )
                )
            payment_distribution.sort(key=lambda x: x.total_revenue, reverse=True)

        # Pareto Summary Text
        top_80_count = sum(1 for p in top_products if p.is_pareto_top_80)
        total_skus = len(top_products)
        sku_pct = round((top_80_count / total_skus) * 100, 1) if total_skus > 0 else 0.0
        pareto_summary = (
            f"Pareto 80/20 Analysis: {top_80_count} of {total_skus} SKUs ({sku_pct}%) account for 80% of total revenue. "
            "Inventory and promotional budgets should prioritize these high-velocity core catalog items."
        )

        return ProductAnalyticsResult(
            top_products=top_products,
            payment_distribution=payment_distribution,
            pareto_80_20_summary=pareto_summary,
        )
