"""
VYTRON AIOps — Shared Pydantic Schemas
Single source of truth for all telemetry, heartbeat, and API payloads.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ───────────────────────────────────────────────────────────────

class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Category(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    NETWORK = "network"
    SECURITY = "security"
    APPLICATION = "application"
    DATABASE = "database"


class DetectionMethod(str, Enum):
    RULE = "rule"
    STATISTICAL = "statistical"
    LLM = "llm"
    CORRELATION = "correlation"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    RETRYABLE = "retryable"
    FAILED = "failed"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTED = "executed"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class HealthState(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class CollectorConfigStatus(str, Enum):
    CONFIGURED = "configured"
    PENDING = "pending"
    ERROR = "error"


class ServerType(str, Enum):
    APPLICATION = "application"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    WEB = "web"
    STORAGE = "storage"
    NETWORK = "network"
    BACKUP = "backup"
    INTERNAL = "internal"


# ── Helper ──────────────────────────────────────────────────────────────

def generate_id(prefix: str = "") -> str:
    short = uuid.uuid4().hex[:12].upper()
    return f"{prefix}-{short}" if prefix else short


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── Telemetry Schemas ───────────────────────────────────────────────────

class RawTelemetryEvent(BaseModel):
    """Raw telemetry from the simulator → collector ingestion endpoint."""
    source_id: str
    timestamp: datetime
    metric: str
    value: float
    category: Category = Category.INFRASTRUCTURE
    metadata: dict[str, Any] = Field(default_factory=dict)
    event_type: str = "metric"

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: Any) -> datetime:
        if isinstance(v, str):
            v = datetime.fromisoformat(v)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v


class ApprovedTelemetryPayload(BaseModel):
    """
    Allow-listed metadata payload sent from collector → backend.
    Constructed explicitly from approved fields only.
    Never serialized from raw input.
    """
    payload_id: str = Field(default_factory=lambda: generate_id("PAYLOAD"))
    tenant_id: str = "TENANT-01"
    collector_id: str = "COLLECTOR-01"
    source_id: str
    timestamp: datetime
    metric: str
    value: float
    severity: Severity = Severity.INFO
    category: Category = Category.INFRASTRUCTURE
    anomaly_detected: bool = False
    detection_method: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_utc(cls, v: Any) -> datetime:
        if isinstance(v, str):
            v = datetime.fromisoformat(v)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v


# ── Heartbeat Schema ───────────────────────────────────────────────────

class CollectorHeartbeat(BaseModel):
    collector_id: str = "COLLECTOR-01"
    tenant_id: str = "TENANT-01"
    timestamp: datetime = Field(default_factory=utc_now)
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    software_version: str = "1.0.0"
    configuration_status: CollectorConfigStatus = CollectorConfigStatus.CONFIGURED
    source_count: int = 0


# ── Egress Proof Schema ────────────────────────────────────────────────

class EgressRecord(BaseModel):
    audit_id: str = Field(default_factory=lambda: generate_id("AUDIT"))
    payload_id: str
    policy_result: str  # "approved" | "partial" | "blocked"
    approved_fields: list[str]
    blocked_fields: list[str]
    transmission_status: str  # mirrors DeliveryStatus
    timestamp: datetime = Field(default_factory=utc_now)
    serialized_payload: str  # exact JSON that was/would be sent


# ── Detection Evidence Schemas ──────────────────────────────────────────

class RuleDetectionResult(BaseModel):
    rule_id: str
    source_id: str
    metric: str
    observed_value: float
    threshold: float
    severity: Severity
    timestamp: datetime
    description: str


class StatisticalDetectionResult(BaseModel):
    source_id: str
    metric: str
    observed_value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    deviation_threshold: float
    severity: Severity
    timestamp: datetime
    sample_count: int


class CorrelationGroup(BaseModel):
    incident_id: str = Field(default_factory=lambda: generate_id("INC"))
    alert_ids: list[str]
    source_ids: list[str]
    categories: list[str]
    time_window_start: datetime
    time_window_end: datetime
    severity: Severity
    title: str


# ── LLM Schemas ─────────────────────────────────────────────────────────

class LLMAnalysisRequest(BaseModel):
    incident_id: str
    alerts: list[dict[str, Any]]
    metrics_context: list[dict[str, Any]]
    server_info: dict[str, Any] = Field(default_factory=dict)


class LLMAnalysisResponse(BaseModel):
    incident_id: str
    summary: str
    contributing_factors: list[str]
    severity_rationale: str
    confidence: str  # "high" | "medium" | "low"
    recommended_steps: list[str]
    raw_response: Optional[str] = None


# ── Recommendation Schema ──────────────────────────────────────────────

class RecommendationPayload(BaseModel):
    recommendation_id: str = Field(default_factory=lambda: generate_id("REC"))
    incident_id: str
    explanation: str
    recommended_action: str
    llm_generated: bool = False
    approval_status: ApprovalStatus = ApprovalStatus.PENDING


# ── Remediation Schemas ─────────────────────────────────────────────────

class RemediationApproval(BaseModel):
    recommendation_id: str
    approved_by: str = "operator"


class RemediationExecution(BaseModel):
    recommendation_id: str
    executed_by: str = "operator"


class RemediationRollback(BaseModel):
    recommendation_id: str
    rolled_back_by: str = "operator"
    reason: str = ""


# ── API Response Wrappers ───────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Any = None


class TelemetryAck(BaseModel):
    payload_id: str
    accepted: bool
    message: str = "accepted"
