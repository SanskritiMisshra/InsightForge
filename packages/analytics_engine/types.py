"""
Type definitions and Pydantic schemas for InsightForge Analytics Engine.
Adheres strictly to PRD and ARCHITECTURE schemas.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class DatasetColumn(BaseModel):
    name: str
    inferred_type: str
    semantic_role: Optional[str] = None
    confidence: float = 1.0
    sample_values: List[Any] = Field(default_factory=list)


class DatasetMetadata(BaseModel):
    id: str
    name: str
    version: str = "v1"
    row_count: int
    column_count: int
    file_size_bytes: int
    sha256_hash: str
    parent_hash: Optional[str] = None
    created_at: str
    columns: List[DatasetColumn]


class QualityIssue(BaseModel):
    issue_type: str
    severity: str  # HIGH, MEDIUM, LOW, INFO
    column_name: str
    affected_rows: int
    action_taken: str
    justification: str


class QualityProfile(BaseModel):
    overall_score: int
    completeness_score: int
    uniqueness_score: int
    validity_score: int
    consistency_score: int
    total_rows: int
    total_cells: int
    null_cells: int
    duplicate_rows: int
    outlier_count: int
    issues: List[QualityIssue]


class CleaningAuditEntry(BaseModel):
    step_number: int
    operation: str
    column_affected: str
    rows_modified: int
    description: str
    justification: str
    timestamp: str


class CleaningResult(BaseModel):
    cleaned_dataset_id: str
    version: str = "v2"
    original_rows: int
    cleaned_rows: int
    dropped_duplicates: int
    imputed_cells: int
    original_sha256: str
    cleaned_sha256: str
    audit_log: List[CleaningAuditEntry]


class NumericHistogram(BaseModel):
    column_name: str
    bins: List[Dict[str, Any]]  # {"bin_start": float, "bin_end": float, "count": int}


class CategoryBreakdown(BaseModel):
    column_name: str
    breakdown: List[Dict[str, Any]]  # {"category": str, "count": int, "percentage": float, "revenue": float}


class CorrelationItem(BaseModel):
    x: str
    y: str
    correlation: float


class EDAResult(BaseModel):
    summary_stats: List[Dict[str, Any]]
    histograms: List[NumericHistogram]
    category_breakdowns: List[CategoryBreakdown]
    correlation_matrix: List[CorrelationItem]
    monthly_revenue: List[Dict[str, Any]]
    methodology_note: str = (
        "Statistical Note: Pearson correlation measures linear association between numeric variables. "
        "Association does not imply causal relationship."
    )


class RFMSegmentSummary(BaseModel):
    name: str
    code: str
    customer_count: int
    customer_pct: float
    total_revenue: float
    revenue_pct: float
    avg_order_value: float
    avg_recency_days: float
    avg_frequency: float
    color: str
    description: str


class RFMAnalysisResult(BaseModel):
    reference_date: str
    total_customers: int
    segments: List[RFMSegmentSummary]
    grid_5x5: List[List[Dict[str, Any]]]
    rules_disclaimer: str


class ProductMetric(BaseModel):
    sku: str
    product_name: str
    category: str
    units_sold: int
    revenue: float
    revenue_pct: float
    cumulative_revenue_pct: float
    is_pareto_top_80: bool


class PaymentMethodDistribution(BaseModel):
    payment_method: str
    transaction_count: int
    total_revenue: float
    revenue_pct: float


class ProductAnalyticsResult(BaseModel):
    top_products: List[ProductMetric]
    payment_distribution: List[PaymentMethodDistribution]
    pareto_80_20_summary: str


class SQLQueryResult(BaseModel):
    query: str
    columns: List[str]
    column_types: List[str]
    rows: List[List[Any]]
    row_count: int
    execution_time_ms: float
    is_read_only: bool = True
    applied_limit: int = 500


class DAXMeasure(BaseModel):
    name: str
    formula: str
    format_string: str
    description: str
    category: str


class StarSchemaTable(BaseModel):
    name: str
    type: str  # fact or dimension
    columns: List[Dict[str, str]]
    primary_key: Optional[str] = None
    foreign_keys: Optional[List[Dict[str, str]]] = None


class StarSchemaModel(BaseModel):
    tables: List[StarSchemaTable]
    relationships: List[Dict[str, Any]]
    dax_measures: List[DAXMeasure]


class DeterministicInsight(BaseModel):
    id: str
    title: str
    category: str  # REVENUE, CUSTOMER, PRODUCT, DATA_QUALITY, RISK
    severity: str  # CRITICAL, HIGH, MEDIUM, POSITIVE, INFO
    finding: str
    business_impact: str
    actionable_recommendation: str
    confidence: float = 1.0
    metric_refs: List[str]
    evidence_key: str


class EvidencePayload(BaseModel):
    metric_name: str
    formatted_value: str
    raw_value: Any
    deterministic_formula: str
    underlying_sql: str
    dataset_version: str
    sha256_hash: str
    lineage_steps: List[Dict[str, Any]]
    sample_records: List[Dict[str, Any]]
