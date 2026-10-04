"""
InsightForge Analytics Engine
Deterministic, audit-traceable data analytics and business intelligence engine.
Follows PRD, DESIGN, ARCHITECTURE, and DATABASE specifications.
"""

from .pipeline import AnalyticsPipeline
from .types import (
    DatasetMetadata,
    QualityProfile,
    CleaningAuditEntry,
    EDAResult,
    RFMAnalysisResult,
    StarSchemaModel,
    DeterministicInsight,
    EvidencePayload,
)

from .number_guard import NumberGuard, VerificationReport

__all__ = [
    "AnalyticsPipeline",
    "DatasetMetadata",
    "QualityProfile",
    "CleaningAuditEntry",
    "EDAResult",
    "RFMAnalysisResult",
    "StarSchemaModel",
    "DeterministicInsight",
    "EvidencePayload",
    "NumberGuard",
    "VerificationReport",
]
