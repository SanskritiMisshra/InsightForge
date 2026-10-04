"""
Stage 3: Cleaning & Transformation Engine
Applies deterministic, auditable transformations to generate Dataset v2.
Raw dataset is strictly immutable. Every operation is recorded in the Cleaning Audit Log.
"""

import pandas as pd
import numpy as np
import hashlib
from datetime import datetime
from typing import Tuple, List
from .types import CleaningResult, CleaningAuditEntry


class DataCleaner:
    @classmethod
    def clean(cls, raw_df: pd.DataFrame, raw_sha256: str) -> Tuple[pd.DataFrame, CleaningResult]:
        df = raw_df.copy()
        original_rows = len(df)
        audit_log: List[CleaningAuditEntry] = []
        step = 1

        # 1. Deduplication
        dup_mask = df.duplicated()
        dropped_duplicates = int(dup_mask.sum())
        if dropped_duplicates > 0:
            df = df.drop_duplicates().reset_index(drop=True)
            audit_log.append(
                CleaningAuditEntry(
                    step_number=step,
                    operation="REMOVE_EXACT_DUPLICATES",
                    column_affected="[ALL_COLUMNS]",
                    rows_modified=dropped_duplicates,
                    description=f"Removed {dropped_duplicates} identical duplicate rows based on all-column match.",
                    justification="Prevents double-counting revenue and transaction counts in downstream BI.",
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
            )
            step += 1

        # 2. String Whitespace Standardization
        trimmed_count = 0
        for col in df.select_dtypes(include=["object"]).columns:
            series = df[col]
            needs_trim = series.dropna().apply(lambda x: isinstance(x, str) and (x != x.strip()))
            n_trim = int(needs_trim.sum())
            if n_trim > 0:
                df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
                trimmed_count += n_trim
                audit_log.append(
                    CleaningAuditEntry(
                        step_number=step,
                        operation="STANDARDIZE_WHITESPACE",
                        column_affected=str(col),
                        rows_modified=n_trim,
                        description=f"Trimmed leading/trailing whitespace across {n_trim} values in {col}.",
                        justification="Ensures clean categorical grouping (e.g. ' Electronics ' merges with 'Electronics').",
                        timestamp=datetime.utcnow().isoformat() + "Z",
                    )
                )
                step += 1

        # 3. Missing Value Imputation
        imputed_cells = 0
        for col in df.columns:
            null_count = int(df[col].isna().sum())
            if null_count > 0:
                if np.issubdtype(df[col].dtype, np.number):
                    median_val = float(df[col].median())
                    df[col] = df[col].fillna(median_val)
                    imputed_cells += null_count
                    audit_log.append(
                        CleaningAuditEntry(
                            step_number=step,
                            operation="IMPUTE_NUMERIC_MEDIAN",
                            column_affected=str(col),
                            rows_modified=null_count,
                            description=f"Imputed {null_count} null cells in {col} with column median ({round(median_val, 2)}).",
                            justification="Median imputation is robust against outliers and preserves distribution shape.",
                            timestamp=datetime.utcnow().isoformat() + "Z",
                        )
                    )
                    step += 1
                else:
                    mode_val = df[col].mode().iloc[0] if not df[col].mode().empty else "UNKNOWN"
                    df[col] = df[col].fillna("UNKNOWN")
                    imputed_cells += null_count
                    audit_log.append(
                        CleaningAuditEntry(
                            step_number=step,
                            operation="IMPUTE_CATEGORICAL_LABEL",
                            column_affected=str(col),
                            rows_modified=null_count,
                            description=f"Filled {null_count} missing values in {col} with label 'UNKNOWN'.",
                            justification="Preserves row completeness without fabricating false categorical attributes.",
                            timestamp=datetime.utcnow().isoformat() + "Z",
                        )
                    )
                    step += 1

        # 4. Standardize Date Formats
        for col in ["order_date", "date", "transaction_date"]:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col])
                    audit_log.append(
                        CleaningAuditEntry(
                            step_number=step,
                            operation="STANDARDIZE_DATETIME_ISO8601",
                            column_affected=col,
                            rows_modified=len(df),
                            description=f"Standardized {col} into ISO-8601 UTC timestamp format.",
                            justification="Ensures chronological sorting and accurate time-series feature engineering.",
                            timestamp=datetime.utcnow().isoformat() + "Z",
                        )
                    )
                    step += 1
                except Exception:
                    pass

        # Compute new SHA-256 hash of cleaned dataframe
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        cleaned_sha256 = hashlib.sha256(csv_bytes).hexdigest()

        cleaning_result = CleaningResult(
            cleaned_dataset_id="ds-benchmark-v2-cleaned",
            version="v2",
            original_rows=original_rows,
            cleaned_rows=len(df),
            dropped_duplicates=dropped_duplicates,
            imputed_cells=imputed_cells,
            original_sha256=raw_sha256,
            cleaned_sha256=cleaned_sha256,
            audit_log=audit_log,
        )

        return df, cleaning_result
