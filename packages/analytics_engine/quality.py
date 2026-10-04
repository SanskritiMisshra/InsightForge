"""
Stage 2: Data Quality Profiler
Calculates multi-dimensional quality scores (Completeness, Uniqueness, Validity, Consistency),
identifies outliers via IQR / Z-score, and creates a transparent Issue Log.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from .types import QualityProfile, QualityIssue


class QualityProfiler:
    @classmethod
    def profile(cls, df: pd.DataFrame) -> QualityProfile:
        total_rows = len(df)
        total_cols = len(df.columns)
        total_cells = total_rows * total_cols

        if total_rows == 0:
            return QualityProfile(
                overall_score=0,
                completeness_score=0,
                uniqueness_score=0,
                validity_score=0,
                consistency_score=0,
                total_rows=0,
                total_cells=0,
                null_cells=0,
                duplicate_rows=0,
                outlier_count=0,
                issues=[],
            )

        # 1. Completeness
        null_cells = int(df.isna().sum().sum())
        completeness_ratio = 1.0 - (null_cells / total_cells if total_cells > 0 else 0)
        completeness_score = max(0, min(100, int(round(completeness_ratio * 100))))

        # 2. Uniqueness
        duplicate_rows = int(df.duplicated().sum())
        uniqueness_ratio = 1.0 - (duplicate_rows / total_rows if total_rows > 0 else 0)
        uniqueness_score = max(0, min(100, int(round(uniqueness_ratio * 100))))

        # 3. Validity (Numeric non-negative checks, date parsing)
        invalid_count = 0
        total_validity_checks = 0

        for col in df.select_dtypes(include=[np.number]).columns:
            total_validity_checks += total_rows
            # check negative values where expected positive
            if col in ["quantity", "unit_price", "total_amount"]:
                invalid_count += int((df[col] < 0).sum())

        validity_ratio = 1.0 - (invalid_count / total_validity_checks if total_validity_checks > 0 else 0)
        validity_score = max(0, min(100, int(round(validity_ratio * 100))))

        # 4. Consistency (e.g. cross-column math: total_amount vs quantity * unit_price)
        consistency_violations = 0
        if "quantity" in df.columns and "unit_price" in df.columns and "total_amount" in df.columns:
            computed = df["quantity"] * df["unit_price"]
            if "discount_pct" in df.columns:
                computed = computed * (1.0 - df["discount_pct"].fillna(0))
            # Flag discrepancies > 1.0 currency unit
            diff = (df["total_amount"] - computed).abs()
            consistency_violations = int((diff > 1.0).sum())

        consistency_ratio = 1.0 - (consistency_violations / total_rows if total_rows > 0 else 0)
        consistency_score = max(0, min(100, int(round(consistency_ratio * 100))))

        # Overall weighted score: 0.30 Completeness + 0.25 Uniqueness + 0.25 Validity + 0.20 Consistency
        overall_score = int(round(
            0.30 * completeness_score +
            0.25 * uniqueness_score +
            0.25 * validity_score +
            0.20 * consistency_score
        ))

        # Detect Outliers (IQR method)
        outlier_count = 0
        outlier_cols = []
        for col in df.select_dtypes(include=[np.number]).columns:
            series = df[col].dropna()
            if len(series) > 10:
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    outliers = series[(series < lower) | (series > upper)]
                    if len(outliers) > 0:
                        outlier_count += len(outliers)
                        outlier_cols.append((col, len(outliers), lower, upper))

        # Build Transparent Issue Log
        issues: List[QualityIssue] = []

        if duplicate_rows > 0:
            issues.append(
                QualityIssue(
                    issue_type="EXACT_DUPLICATE_ROWS",
                    severity="HIGH",
                    column_name="[ALL_COLUMNS]",
                    affected_rows=duplicate_rows,
                    action_taken="Deduplicated in v2 pipeline",
                    justification=f"Found {duplicate_rows} redundant exact duplicate records that artificially inflate transaction volume and revenue.",
                )
            )

        # Check null columns
        for col in df.columns:
            nulls = int(df[col].isna().sum())
            if nulls > 0:
                pct = round((nulls / total_rows) * 100, 1)
                sev = "HIGH" if pct > 10 else ("MEDIUM" if pct > 2 else "LOW")
                action = "Impute median/mode" if df[col].dtype in [np.float64, np.int64] else "Tagged as UNKNOWN"
                issues.append(
                    QualityIssue(
                        issue_type="MISSING_VALUES",
                        severity=sev,
                        column_name=str(col),
                        affected_rows=nulls,
                        action_taken=action,
                        justification=f"{nulls} missing values ({pct}%) detected. Handled to ensure downstream analytics do not drop valid rows.",
                    )
                )

        # Check string whitespace
        for col in df.select_dtypes(include=["object"]).columns:
            # check leading/trailing spaces
            has_spaces = df[col].dropna().apply(lambda x: isinstance(x, str) and (x != x.strip())).sum()
            if has_spaces > 0:
                issues.append(
                    QualityIssue(
                        issue_type="WHITESPACE_INCONSISTENCY",
                        severity="LOW",
                        column_name=str(col),
                        affected_rows=int(has_spaces),
                        action_taken="Trim whitespace",
                        justification=f"{has_spaces} values contain leading/trailing whitespace which could split aggregate groups.",
                    )
                )

        if outlier_count > 0:
            issues.append(
                QualityIssue(
                    issue_type="STATISTICAL_OUTLIERS",
                    severity="INFO",
                    column_name=", ".join([c[0] for c in outlier_cols[:3]]),
                    affected_rows=outlier_count,
                    action_taken="Flagged in EDA; preserved in raw data",
                    justification=f"Detected {outlier_count} IQR outliers across numeric fields. Retained in analytical dataset to avoid altering true retail sales distribution.",
                )
            )

        return QualityProfile(
            overall_score=overall_score,
            completeness_score=completeness_score,
            uniqueness_score=uniqueness_score,
            validity_score=validity_score,
            consistency_score=consistency_score,
            total_rows=total_rows,
            total_cells=total_cells,
            null_cells=null_cells,
            duplicate_rows=duplicate_rows,
            outlier_count=outlier_count,
            issues=issues,
        )
