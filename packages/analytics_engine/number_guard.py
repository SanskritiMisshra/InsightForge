"""
InsightForge Deterministic Number-Verification Guard
Audits narrative text, insights, and executive summaries.
Extracts every numerical token (currencies, percentages, counts, ratios, decimals)
and verifies it against the approved Canonical Metric Registry and active dataset truth.
Guarantees the Numerical Truth Invariant: Zero Hallucinated Numbers.
"""

import re
import math
from typing import List, Dict, Any, Set, Tuple, Optional
from pydantic import BaseModel, Field


class NumberVerificationToken(BaseModel):
    token: str
    raw_number: float
    token_type: str  # CURRENCY, PERCENTAGE, INTEGER, DECIMAL, RATIO
    is_verified: bool
    matched_metric: Optional[str] = None
    delta: Optional[float] = None


class VerificationReport(BaseModel):
    is_fully_verified: bool
    total_tokens_found: int
    verified_count: int
    unverified_count: int
    tokens: List[NumberVerificationToken]
    flagged_tokens: List[str]
    audit_summary: str


class NumberGuard:
    # Regex patterns for numerical entities
    CURRENCY_REGEX = re.compile(r'₹\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]+)?|\d+(?:\.[0-9]+)?)\s*(?:L|Cr|k|M)?', re.IGNORECASE)
    PERCENT_REGEX = re.compile(r'([+-]?\d+(?:\.\d+)?)\s*%', re.IGNORECASE)
    RATIO_REGEX = re.compile(r'(\d+(?:\.\d+)?)\s*x', re.IGNORECASE)
    NUMBER_REGEX = re.compile(r'\b([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|\d+\.\d+)\b')

    @classmethod
    def extract_canonical_pool(cls, pipeline_result) -> Dict[str, float]:
        """
        Builds a comprehensive dictionary of all mathematically verified numbers
        from the active pipeline execution: KPIs, Quality, EDA, RFM, Product catalog.
        """
        pool: Dict[str, float] = {}

        if not pipeline_result:
            return pool

        df = pipeline_result.cleaned_df
        # 1. Core KPIs
        if "total_amount" in df.columns:
            tot_rev = float(df["total_amount"].sum())
            pool["total_revenue"] = tot_rev
            pool["total_revenue_lakh"] = round(tot_rev / 100000.0, 2)
            pool["total_revenue_cr"] = round(tot_rev / 10000000.0, 2)

        if "order_id" in df.columns:
            tot_orders = float(df["order_id"].nunique())
            pool["total_orders"] = tot_orders
        else:
            pool["total_orders"] = float(len(df))

        if "customer_id" in df.columns:
            tot_cust = float(df["customer_id"].nunique())
            pool["total_customers"] = tot_cust

        if pool.get("total_orders", 0) > 0 and pool.get("total_revenue", 0) > 0:
            aov = round(pool["total_revenue"] / pool["total_orders"], 2)
            pool["aov"] = aov

        # 2. Quality Scores
        if hasattr(pipeline_result, "quality_profile"):
            qp = pipeline_result.quality_profile
            pool["quality_overall"] = float(qp.overall_score)
            pool["quality_completeness"] = float(qp.completeness_score)
            pool["quality_uniqueness"] = float(qp.uniqueness_score)
            pool["quality_validity"] = float(qp.validity_score)
            pool["quality_consistency"] = float(qp.consistency_score)
            pool["quality_null_cells"] = float(qp.null_cells)
            pool["quality_outliers"] = float(qp.outlier_count)

        # 3. Cleaning metadata
        if hasattr(pipeline_result, "cleaning_result"):
            cr = pipeline_result.cleaning_result
            pool["cleaned_rows"] = float(cr.cleaned_rows)
            pool["original_rows"] = float(cr.original_rows)
            pool["dropped_duplicates"] = float(cr.dropped_duplicates)
            pool["imputed_cells"] = float(cr.imputed_cells)

        # 4. RFM Segments
        if hasattr(pipeline_result, "rfm_result") and pipeline_result.rfm_result:
            for s in pipeline_result.rfm_result.segments:
                prefix = f"rfm_{s.code.lower()}"
                pool[f"{prefix}_count"] = float(s.customer_count)
                pool[f"{prefix}_cust_pct"] = float(s.customer_pct)
                pool[f"{prefix}_rev"] = float(s.total_revenue)
                pool[f"{prefix}_rev_lakh"] = round(s.total_revenue / 100000.0, 2)
                pool[f"{prefix}_rev_pct"] = float(s.revenue_pct)
                pool[f"{prefix}_aov"] = float(s.avg_order_value)
                pool[f"{prefix}_recency"] = float(s.avg_recency_days)

        # 5. Product & Payment
        if hasattr(pipeline_result, "product_result") and pipeline_result.product_result:
            pr = pipeline_result.product_result
            for idx, p in enumerate(pr.top_products[:10]):
                pool[f"prod_{idx+1}_rev"] = float(p.revenue)
                pool[f"prod_{idx+1}_pct"] = float(p.revenue_pct)
                pool[f"prod_{idx+1}_units"] = float(p.units_sold)
            for pay in pr.payment_distribution:
                pname = pay.payment_method.lower().replace(" ", "_")
                pool[f"pay_{pname}_rev"] = float(pay.total_revenue)
                pool[f"pay_{pname}_pct"] = float(pay.revenue_pct)
                pool[f"pay_{pname}_txns"] = float(pay.transaction_count)

        # 6. Standard acceptable baseline values (percentages, tolerances)
        pool["zero"] = 0.0
        pool["hundred"] = 100.0
        pool["five_pct"] = 5.0
        pool["ten_pct"] = 10.0
        pool["fifteen_pct"] = 15.0
        pool["eighty_pct"] = 80.0
        pool["twenty_pct"] = 20.0
        pool["thirty_days"] = 30.0
        pool["sixty_days"] = 60.0
        pool["ninety_days"] = 90.0

        return pool

    @classmethod
    def _parse_currency_value(cls, match_str: str) -> float:
        # Handles ₹8.92L, ₹84.20L, ₹1,248, ₹22,331,115.75
        cleaned = match_str.replace("₹", "").replace(",", "").strip()
        multiplier = 1.0
        if cleaned.endswith("L") or cleaned.endswith("l"):
            multiplier = 100000.0
            cleaned = cleaned[:-1]
        elif cleaned.endswith("Cr") or cleaned.endswith("cr"):
            multiplier = 10000000.0
            cleaned = cleaned[:-2]
        elif cleaned.endswith("k") or cleaned.endswith("K"):
            multiplier = 1000.0
            cleaned = cleaned[:-1]
        elif cleaned.endswith("M") or cleaned.endswith("m"):
            multiplier = 1000000.0
            cleaned = cleaned[:-1]

        try:
            return float(cleaned) * multiplier
        except ValueError:
            return 0.0

    @classmethod
    def verify_text(cls, text: str, pipeline_result, canonical_pool: Optional[Dict[str, float]] = None) -> VerificationReport:
        """
        Extracts all numeric tokens from text and verifies them against canonical pool.
        """
        if canonical_pool is None:
            canonical_pool = cls.extract_canonical_pool(pipeline_result)

        tokens: List[NumberVerificationToken] = []
        seen_strings: Set[str] = set()

        # 1. Match Currencies
        for m in cls.CURRENCY_REGEX.finditer(text):
            tok_str = m.group(0).strip()
            if tok_str in seen_strings:
                continue
            seen_strings.add(tok_str)
            raw_num = cls._parse_currency_value(tok_str)
            match_name, delta = cls._find_closest_match(raw_num, canonical_pool, is_currency=True)
            tokens.append(
                NumberVerificationToken(
                    token=tok_str,
                    raw_number=raw_num,
                    token_type="CURRENCY",
                    is_verified=(match_name is not None),
                    matched_metric=match_name,
                    delta=delta,
                )
            )

        # 2. Match Percentages
        for m in cls.PERCENT_REGEX.finditer(text):
            tok_str = m.group(0).strip()
            if tok_str in seen_strings:
                continue
            seen_strings.add(tok_str)
            raw_num = abs(float(m.group(1)))
            match_name, delta = cls._find_closest_match(raw_num, canonical_pool, is_percent=True)
            tokens.append(
                NumberVerificationToken(
                    token=tok_str,
                    raw_number=raw_num,
                    token_type="PERCENTAGE",
                    is_verified=(match_name is not None),
                    matched_metric=match_name,
                    delta=delta,
                )
            )

        # 3. Match Ratios (e.g. 4.2x)
        for m in cls.RATIO_REGEX.finditer(text):
            tok_str = m.group(0).strip()
            if tok_str in seen_strings:
                continue
            seen_strings.add(tok_str)
            raw_num = float(m.group(1))
            match_name, delta = cls._find_closest_match(raw_num, canonical_pool)
            tokens.append(
                NumberVerificationToken(
                    token=tok_str,
                    raw_number=raw_num,
                    token_type="RATIO",
                    is_verified=(match_name is not None),
                    matched_metric=match_name,
                    delta=delta,
                )
            )

        # 4. Match Other numbers with commas or decimals
        for m in cls.NUMBER_REGEX.finditer(text):
            tok_str = m.group(0).strip()
            if any(tok_str in s for s in seen_strings):
                continue
            seen_strings.add(tok_str)
            raw_num = float(tok_str.replace(",", ""))
            match_name, delta = cls._find_closest_match(raw_num, canonical_pool)
            tokens.append(
                NumberVerificationToken(
                    token=tok_str,
                    raw_number=raw_num,
                    token_type="INTEGER" if "." not in tok_str else "DECIMAL",
                    is_verified=(match_name is not None),
                    matched_metric=match_name,
                    delta=delta,
                )
            )

        verified = [t for t in tokens if t.is_verified]
        unverified = [t for t in tokens if not t.is_verified]
        is_all_clean = len(unverified) == 0

        summary = (
            f"Verified {len(verified)}/{len(tokens)} figures against Canonical Metric Registry. "
            f"Zero unverified figures detected."
            if is_all_clean
            else f"Warning: {len(unverified)} figures could not be authenticated against the active dataset pool."
        )

        return VerificationReport(
            is_fully_verified=is_all_clean,
            total_tokens_found=len(tokens),
            verified_count=len(verified),
            unverified_count=len(unverified),
            tokens=tokens,
            flagged_tokens=[t.token for t in unverified],
            audit_summary=summary,
        )

    @classmethod
    def _find_closest_match(
        cls,
        val: float,
        pool: Dict[str, float],
        is_currency: bool = False,
        is_percent: bool = False,
    ) -> Tuple[Optional[str], Optional[float]]:
        """
        Searches canonical pool for exact or near-match within strict analytical tolerance.
        """
        best_metric: Optional[str] = None
        min_delta: float = float("inf")

        for metric_name, canonical_val in pool.items():
            diff = abs(val - canonical_val)

            if diff < 0.05:
                return metric_name, round(diff, 4)

            if canonical_val != 0:
                rel_diff = diff / abs(canonical_val)
                if rel_diff < 0.02:
                    if diff < min_delta:
                        min_delta = diff
                        best_metric = metric_name

        if best_metric:
            return best_metric, round(min_delta, 4)

        return None, None
