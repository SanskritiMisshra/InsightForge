"""
Stage 4: Semantic Schema Mapper
Infers semantic business roles for columns in e-commerce/retail datasets.
Assigns confidence scores and validates data compatibility.
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Any
from .types import DatasetColumn


ROLE_PATTERNS = {
    "TRANSACTION_DATE": [r"order_?date", r"date", r"trans(action)?_?date", r"created_?at", r"timestamp"],
    "CUSTOMER_ID": [r"cust(omer)?_?id", r"user_?id", r"client_?id", r"buyer_?id"],
    "ORDER_ID": [r"order_?id", r"invoice_?(no|num|id)?", r"trans(action)?_?id", r"receipt_?id"],
    "REVENUE": [r"total_?amount", r"revenue", r"sales", r"price_?total", r"net_?amount", r"amount"],
    "QUANTITY": [r"quantity", r"qty", r"items?_?count", r"volume", r"units"],
    "UNIT_PRICE": [r"unit_?price", r"item_?price", r"price", r"cost_?per_?unit"],
    "PRODUCT_ID": [r"product_?id", r"sku", r"item_?id", r"part_?number"],
    "PRODUCT_NAME": [r"product_?name", r"item_?name", r"title", r"description"],
    "CATEGORY": [r"category", r"department", r"prod(uct)?_?category", r"group"],
    "PAYMENT_METHOD": [r"payment_?method", r"payment_?type", r"pay_?mode", r"tender"],
    "GEOGRAPHY": [r"city", r"region", r"state", r"country", r"zip", r"postal"],
}


class SchemaMapper:
    @classmethod
    def map_columns(cls, df: pd.DataFrame) -> List[DatasetColumn]:
        results: List[DatasetColumn] = []

        for col in df.columns:
            col_str = str(col).lower().strip()
            inferred_type = str(df[col].dtype)
            sample_vals = [str(x) for x in df[col].dropna().head(3).tolist()]

            matched_role = None
            confidence = 0.50

            for role, patterns in ROLE_PATTERNS.items():
                for pat in patterns:
                    if re.fullmatch(pat, col_str):
                        matched_role = role
                        confidence = 0.99
                        break
                    elif re.search(pat, col_str):
                        matched_role = role
                        confidence = 0.85
                        break
                if matched_role and confidence >= 0.85:
                    break

            # Fallback heuristic if not matched by name
            if not matched_role:
                if "date" in inferred_type or "datetime" in inferred_type:
                    matched_role = "TRANSACTION_DATE"
                    confidence = 0.70
                elif np.issubdtype(df[col].dtype, np.number):
                    matched_role = "NUMERIC_METRIC"
                    confidence = 0.60
                else:
                    matched_role = "CATEGORICAL_DIMENSION"
                    confidence = 0.60

            results.append(
                DatasetColumn(
                    name=str(col),
                    inferred_type=inferred_type,
                    semantic_role=matched_role,
                    confidence=confidence,
                    sample_values=sample_vals,
                )
            )

        return results
