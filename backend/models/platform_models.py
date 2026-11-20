"""
Platform Database Models (platform.db - Tier 2)
Strictly adheres to TRD Table 5.2:
- tenants
- collectors
- servers
- metrics
- alerts
- incidents
- incident_alerts
- recommendations
- audit_logs
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base


def utc_now_str():
    return datetime.now(timezone.utc).isoformat()


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id = Column(String(50), primary_key=True)
    tenant_name = Column(String(100), nullable=False)
    created_at = Column(String(50), default=utc_now_str)


class Collector(Base):
    __tablename__ = "collectors"

    collector_id = Column(String(50), primary_key=True)
    tenant_id = Column(String(50), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    status = Column(String(50), default="online", index=True)  # online, offline, degraded
    last_seen = Column(String(50), default=utc_now_str, index=True)
    software_version = Column(String(50), default="1.0.0")
    cpu_usage = Column(Float, default=0.0)
    memory_usage = Column(Float, default=0.0)
    configuration_status = Column(String(50), default="configured")


class Server(Base):
    __tablename__ = "servers"

    server_id = Column(String(50), primary_key=True)
    tenant_id = Column(String(50), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    collector_id = Column(String(50), ForeignKey("collectors.collector_id"), nullable=False)
    server_name = Column(String(100), nullable=False)
    server_type = Column(String(50), nullable=False)
    status = Column(String(50), default="excellent", index=True)  # excellent, good, fair, poor


class Metric(Base):
    __tablename__ = "metrics"

    metric_id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(50), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    server_id = Column(String(50), ForeignKey("servers.server_id"), nullable=False, index=True)
    payload_id = Column(String(50), unique=True, nullable=False, index=True)  # Enforces Idempotency
    metric_name = Column(String(50), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    event_timestamp = Column(String(50), nullable=False, index=True)  # Canonical event time in UTC
    received_timestamp = Column(String(50), default=utc_now_str)      # Time of ingest into SaaS


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(String(50), primary_key=True)
    tenant_id = Column(String(50), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    server_id = Column(String(50), ForeignKey("servers.server_id"), nullable=False, index=True)
    metric_id = Column(Integer, ForeignKey("metrics.metric_id"), nullable=True)
    detection_method = Column(String(50), nullable=False)  # rule, statistical, llm
    severity = Column(String(50), nullable=False, index=True)  # info, warning, critical
    description = Column(Text, nullable=False)
    created_at = Column(String(50), default=utc_now_str, index=True)
    status = Column(String(50), default="active", index=True)  # active, acknowledged, resolved


class Incident(Base):
    __tablename__ = "incidents"

    incident_id = Column(String(50), primary_key=True)
    tenant_id = Column(String(50), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    severity = Column(String(50), nullable=False, index=True)  # warning, critical
    summary = Column(Text, nullable=False)
    status = Column(String(50), default="open", index=True)  # open, investigating, resolved, closed
    created_at = Column(String(50), default=utc_now_str, index=True)
    updated_at = Column(String(50), default=utc_now_str)


class IncidentAlert(Base):
    __tablename__ = "incident_alerts"

    incident_id = Column(String(50), ForeignKey("incidents.incident_id"), primary_key=True)
    alert_id = Column(String(50), ForeignKey("alerts.alert_id"), primary_key=True)


class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id = Column(String(50), primary_key=True)
    incident_id = Column(String(50), ForeignKey("incidents.incident_id"), nullable=False, index=True)
    explanation = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=False)
    llm_generated = Column(Boolean, default=False)
    approval_status = Column(String(50), default="pending", index=True)  # pending, approved, executed, rolled_back
    created_at = Column(String(50), default=utc_now_str)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id = Column(String(50), primary_key=True)
    tenant_id = Column(String(50), ForeignKey("tenants.tenant_id"), nullable=False, index=True)
    actor = Column(String(50), default="system")
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=False)
    timestamp = Column(String(50), default=utc_now_str, index=True)
    details = Column(Text, nullable=True)
