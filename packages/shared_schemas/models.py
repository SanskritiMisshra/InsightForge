"""
Shared Pydantic schemas and types for InsightForge.
Defines canonical contracts consumed across backend, analytics engine, and API.
Conforms strictly to DATABASE.md, API_SPEC.md, and ANALYTICS_SPEC.md.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Organization(BaseModel):
    id: str
    name: str
    slug: str
    created_at: str


class Workspace(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: str
    created_at: str


class User(BaseModel):
    id: str
    email: str
    full_name: str
    role: str = "ANALYST"
    is_active: bool = True
    created_at: str


class Project(BaseModel):
    id: str
    workspace_id: str
    name: str
    domain: str = "retail"
    description: Optional[str] = None
    created_at: str


class Dataset(BaseModel):
    id: str
    project_id: str
    name: str
    original_filename: str
    created_at: str


class DatasetVersion(BaseModel):
    id: str
    dataset_id: str
    version_number: int  # 1 for raw immutable, 2 for cleaned
    version_label: str  # 'v1 · Raw' or 'v2 · Cleaned'
    sha256_hash: str
    parent_version_id: Optional[str] = None
    row_count: int
    column_count: int
    file_size_bytes: int
    is_active: bool = True
    created_at: str


class MetricRecord(BaseModel):
    id: str
    run_id: str
    dataset_version_id: str
    metric_key: str
    metric_name: str
    category: str
    formatted_value: str
    numeric_value: float
    unit: str
    grain: str
    formula: str
    underlying_sql: str
    sha256_hash: str
    created_at: str


class QualityProfileRecord(BaseModel):
    id: str
    dataset_version_id: str
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
    issues_json: List[Dict[str, Any]]
    created_at: str


class CleaningLogEntry(BaseModel):
    id: str
    dataset_version_id: str
    step_number: int
    operation: str
    column_affected: str
    rows_modified: int
    description: str
    justification: str
    created_at: str


class AuditEvent(BaseModel):
    id: str
    organization_id: str
    user_id: str
    event_type: str
    resource_type: str
    resource_id: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    created_at: str
