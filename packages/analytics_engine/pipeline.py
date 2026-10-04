"""
End-to-End Analytics Pipeline Orchestrator
Executes the full 10-stage automated analytics pipeline in accordance with PRD.md:
1. Ingestion & Lineage (SHA-256)
2. Data Quality Profiling (4 Dimensions + Issue Log)
3. Automated Cleaning & Transformation (Dataset v2 + Audit Trail)
4. Semantic Schema Mapping
5. Exploratory Data Analysis (EDA & Pearson Correlations)
6. Customer RFM Segmentation (5x5 Grid & Deterministic Segments)
7. Product & Payment Analytics (Pareto 80/20 & Payment Rails)
8. Deterministic Insights Generation (with MetricRef links)
9. Star Schema & DAX Measures (Kimball Model)
10. Executive Report & Presentation Deck Synthesis
"""

import pandas as pd
import hashlib
from typing import Dict, Any, Optional

from .types import (
    DatasetMetadata,
    QualityProfile,
    CleaningResult,
    EDAResult,
    RFMAnalysisResult,
    ProductAnalyticsResult,
    StarSchemaModel,
    DeterministicInsight,
    SQLQueryResult,
    EvidencePayload,
)
from .ingestion import IngestionEngine
from .quality import QualityProfiler
from .cleaner import DataCleaner
from .schema_mapper import SchemaMapper
from .eda import EDAEngine
from .rfm import RFMEngine
from .product_analytics import ProductAnalyticsEngine
from .sql_sandbox import SQLSandbox
from .star_schema import StarSchemaGenerator
from .insights import InsightsEngine
from .sample_data import generate_benchmark_retail_dataset


class AnalyticsPipelineResult:
    def __init__(
        self,
        raw_df: pd.DataFrame,
        cleaned_df: pd.DataFrame,
        metadata: DatasetMetadata,
        quality_profile: QualityProfile,
        cleaning_result: CleaningResult,
        columns: list,
        eda_result: EDAResult,
        rfm_result: RFMAnalysisResult,
        product_result: ProductAnalyticsResult,
        star_schema: StarSchemaModel,
        insights: list,
    ):
        self.raw_df = raw_df
        self.cleaned_df = cleaned_df
        self.metadata = metadata
        self.quality_profile = quality_profile
        self.cleaning_result = cleaning_result
        self.columns = columns
        self.eda_result = eda_result
        self.rfm_result = rfm_result
        self.product_result = product_result
        self.star_schema = star_schema
        self.insights = insights

    def execute_sql(self, query: str) -> SQLQueryResult:
        return SQLSandbox.execute_query(self.cleaned_df, query)

    def get_evidence(self, metric_key: str) -> EvidencePayload:
        return InsightsEngine.get_evidence_payload(
            metric_key=metric_key,
            df=self.cleaned_df,
            rfm_res=self.rfm_result,
            dataset_version=self.cleaning_result.version + " · Cleaned",
            dataset_sha256=self.cleaning_result.cleaned_sha256,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.model_dump(),
            "quality": self.quality_profile.model_dump(),
            "cleaning": self.cleaning_result.model_dump(),
            "columns": [c.model_dump() for c in self.columns],
            "eda": self.eda_result.model_dump(),
            "rfm": self.rfm_result.model_dump(),
            "products": self.product_result.model_dump(),
            "star_schema": self.star_schema.model_dump(),
            "insights": [i.model_dump() for i in self.insights],
        }


class AnalyticsPipeline:
    @classmethod
    def run_on_dataframe(cls, df: pd.DataFrame, dataset_id: str = "ds-benchmark", filename: str = "retail_sales_2025.csv") -> AnalyticsPipelineResult:
        # Calculate raw SHA-256
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        raw_sha256 = hashlib.sha256(csv_bytes).hexdigest()

        # 1. Ingestion Metadata
        schema_cols = SchemaMapper.map_columns(df)
        metadata = DatasetMetadata(
            id=dataset_id,
            name=filename,
            version="v1",
            row_count=len(df),
            column_count=len(df.columns),
            file_size_bytes=len(csv_bytes),
            sha256_hash=raw_sha256,
            created_at=pd.Timestamp.utcnow().isoformat() + "Z",
            columns=schema_cols,
        )

        # 2. Quality Profiling (on raw data)
        quality_profile = QualityProfiler.profile(df)

        # 3. Automated Cleaning (produces cleaned_df v2)
        cleaned_df, cleaning_result = DataCleaner.clean(df, raw_sha256)

        # 4. Semantic Schema Mapping (on cleaned columns)
        cleaned_cols = SchemaMapper.map_columns(cleaned_df)

        # 5. EDA
        eda_result = EDAEngine.analyze(cleaned_df)

        # 6. Customer RFM Segmentation
        rfm_result = RFMEngine.analyze(cleaned_df)

        # 7. Product & Payment Analytics
        product_result = ProductAnalyticsEngine.analyze(cleaned_df)

        # 8. Deterministic Insights
        insights = InsightsEngine.generate_insights(
            df=cleaned_df,
            rfm_res=rfm_result,
            product_res=product_result,
            quality_res=quality_profile,
            dataset_version="v2",
            dataset_sha256=cleaning_result.cleaned_sha256,
        )

        # 9. Star Schema & DAX
        star_schema = StarSchemaGenerator.generate()

        return AnalyticsPipelineResult(
            raw_df=df,
            cleaned_df=cleaned_df,
            metadata=metadata,
            quality_profile=quality_profile,
            cleaning_result=cleaning_result,
            columns=cleaned_cols,
            eda_result=eda_result,
            rfm_result=rfm_result,
            product_result=product_result,
            star_schema=star_schema,
            insights=insights,
        )

    @classmethod
    def run_on_bytes(cls, content: bytes, filename: str, dataset_id: str = "ds-custom") -> AnalyticsPipelineResult:
        df, _ = IngestionEngine.load_bytes(content, filename, dataset_id)
        return cls.run_on_dataframe(df, dataset_id=dataset_id, filename=filename)

    @classmethod
    def run_benchmark(cls, n_rows: int = 10000) -> AnalyticsPipelineResult:
        df = generate_benchmark_retail_dataset(n_rows=n_rows)
        return cls.run_on_dataframe(df, dataset_id="ds-benchmark", filename="retail_sales_2025.csv")
