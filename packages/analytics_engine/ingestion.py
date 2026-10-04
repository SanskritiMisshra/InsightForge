"""
Stage 1: Ingestion Engine
Handles file parsing, encoding sniffing, delimiter detection, SHA-256 provenance calculation.
"""

import hashlib
import io
import os
import pandas as pd
from datetime import datetime
from typing import Tuple, Dict, Any
from .types import DatasetMetadata, DatasetColumn


class IngestionEngine:
    @staticmethod
    def compute_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def detect_encoding_and_delimiter(sample_bytes: bytes) -> Tuple[str, str]:
        encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252", "iso-8859-1"]
        decoded_text = None
        used_encoding = "utf-8"

        for enc in encodings:
            try:
                decoded_text = sample_bytes[:8192].decode(enc)
                used_encoding = enc
                break
            except (UnicodeDecodeError, Exception):
                continue

        if not decoded_text:
            decoded_text = sample_bytes[:8192].decode("utf-8", errors="replace")
            used_encoding = "utf-8"

        # Sniff delimiter from first non-empty lines
        lines = [line.strip() for line in decoded_text.splitlines() if line.strip()]
        delimiters = [",", "\t", ";", "|"]
        delimiter_scores = {d: 0 for d in delimiters}

        if lines:
            first_line = lines[0]
            for d in delimiters:
                delimiter_scores[d] = first_line.count(d)

        best_delimiter = max(delimiter_scores, key=delimiter_scores.get)
        if delimiter_scores[best_delimiter] == 0:
            best_delimiter = ","

        return used_encoding, best_delimiter

    @classmethod
    def load_bytes(cls, content: bytes, filename: str, dataset_id: str = "ds-benchmark") -> Tuple[pd.DataFrame, DatasetMetadata]:
        sha256_hash = cls.compute_sha256(content)
        file_size = len(content)

        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content))
        elif filename.endswith(".parquet"):
            df = pd.read_parquet(io.BytesIO(content))
        else:
            encoding, delimiter = cls.detect_encoding_and_delimiter(content)
            df = pd.read_csv(io.BytesIO(content), encoding=encoding, sep=delimiter)

        columns = []
        for col in df.columns:
            inferred_type = str(df[col].dtype)
            sample_vals = df[col].dropna().head(3).tolist()
            sample_vals = [str(v) for v in sample_vals]
            columns.append(
                DatasetColumn(
                    name=str(col),
                    inferred_type=inferred_type,
                    sample_values=sample_vals,
                )
            )

        metadata = DatasetMetadata(
            id=dataset_id,
            name=filename,
            version="v1",
            row_count=len(df),
            column_count=len(df.columns),
            file_size_bytes=file_size,
            sha256_hash=sha256_hash,
            created_at=datetime.utcnow().isoformat() + "Z",
            columns=columns,
        )

        return df, metadata
