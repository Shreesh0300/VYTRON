"""
Collector Database Models (collector.db - Tier 1)
Strictly adheres to TRD Table 5.1:
- source_registry
- local_events
- egress_queue
- collector_health
- transfer_audit
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Index
from collector.database import Base


def utc_now_str():
    return datetime.now(timezone.utc).isoformat()


class SourceRegistry(Base):
    __tablename__ = "source_registry"

    source_id = Column(String(50), primary_key=True)
    source_name = Column(String(100), nullable=False)
    source_type = Column(String(50), nullable=False)
    configuration_status = Column(String(50), default="active")
    last_seen = Column(String(50), default=utc_now_str)


class LocalEvent(Base):
    __tablename__ = "local_events"

    event_id = Column(String(50), primary_key=True)
    source_id = Column(String(50), nullable=False, index=True)
    event_timestamp = Column(String(50), nullable=False, index=True)
    event_type = Column(String(50), default="metric")
    event_data = Column(Text, nullable=False)  # Raw unredacted event JSON for local forensic analysis
    processing_status = Column(String(50), default="received", index=True)


class EgressQueue(Base):
    __tablename__ = "egress_queue"

    payload_id = Column(String(50), primary_key=True)
    created_at = Column(String(50), default=utc_now_str)
    payload_json = Column(Text, nullable=False)  # Exact serialized JSON to send
    delivery_status = Column(String(50), default="pending", index=True)  # pending, in_progress, delivered, retryable, failed
    retry_count = Column(Integer, default=0)
    last_attempt_at = Column(String(50), nullable=True)
    acknowledged_at = Column(String(50), nullable=True)


class CollectorHealth(Base):
    __tablename__ = "collector_health"

    collector_id = Column(String(50), primary_key=True)
    heartbeat_timestamp = Column(String(50), default=utc_now_str)
    cpu_usage = Column(Float, default=0.0)
    memory_usage = Column(Float, default=0.0)
    software_version = Column(String(50), default="1.0.0")
    configuration_status = Column(String(50), default="configured")


class TransferAudit(Base):
    __tablename__ = "transfer_audit"

    audit_id = Column(String(50), primary_key=True)
    payload_id = Column(String(50), nullable=False, index=True)
    policy_result = Column(String(50), nullable=False)  # approved, redacted, partial, blocked
    approved_fields = Column(Text, nullable=False)  # JSON array
    blocked_fields = Column(Text, nullable=False)   # JSON array
    transmission_status = Column(String(50), default="queued")
    timestamp = Column(String(50), default=utc_now_str, index=True)
