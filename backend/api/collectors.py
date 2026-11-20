"""
Collectors Management API Router
Handles heartbeat tracking and offline status detection within target SLA (≤ 60s).
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from shared.schemas import CollectorHeartbeat
from backend.database.connection import get_db
from backend.security.auth import verify_collector_api_key
from backend.models.platform_models import Collector, AuditLog
from shared.constants import COLLECTOR_OFFLINE_TIMEOUT_SECONDS, DEFAULT_TENANT_ID

router = APIRouter(prefix="/api/collectors", tags=["Collectors"])


@router.post("/heartbeat")
def record_heartbeat(
    heartbeat: CollectorHeartbeat,
    tenant_id: str = Depends(verify_collector_api_key),
    db: Session = Depends(get_db),
):
    """
    Heartbeat receiver from Tier 1 Local Collectors.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    collector = db.query(Collector).filter_by(collector_id=heartbeat.collector_id).first()

    if not collector:
        collector = Collector(
            collector_id=heartbeat.collector_id,
            tenant_id=tenant_id,
            status="online",
            last_seen=now_str,
            software_version=heartbeat.software_version,
            cpu_usage=heartbeat.cpu_usage,
            memory_usage=heartbeat.memory_usage,
            configuration_status=heartbeat.configuration_status.value,
        )
        db.add(collector)
    else:
        collector.status = "online"
        collector.last_seen = now_str
        collector.cpu_usage = heartbeat.cpu_usage
        collector.memory_usage = heartbeat.memory_usage
        collector.software_version = heartbeat.software_version
        collector.configuration_status = heartbeat.configuration_status.value

    db.commit()
    return {"status": "heartbeat_acknowledged", "timestamp": now_str}


@router.get("")
def list_collectors(
    tenant_id: str = DEFAULT_TENANT_ID,
    db: Session = Depends(get_db),
):
    """
    Lists collectors with real-time computed health states (detects offline status <= 60s).
    """
    collectors = db.query(Collector).filter_by(tenant_id=tenant_id).all()
    now = datetime.now(timezone.utc)
    res = []

    for c in collectors:
        last_dt = datetime.fromisoformat(c.last_seen)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        diff_sec = (now - last_dt).total_seconds()

        # Offline detection logic (Evaluation Requirement: within 60s)
        is_offline = diff_sec > COLLECTOR_OFFLINE_TIMEOUT_SECONDS
        status = "offline" if is_offline else "online"
        health_state = "poor" if is_offline else ("fair" if c.cpu_usage > 80 else "excellent")

        res.append({
            "collector_id": c.collector_id,
            "tenant_id": c.tenant_id,
            "status": status,
            "health_state": health_state,
            "last_seen": c.last_seen,
            "seconds_since_last_seen": round(diff_sec, 1),
            "software_version": c.software_version,
            "cpu_usage": c.cpu_usage,
            "memory_usage": c.memory_usage,
            "configuration_status": c.configuration_status,
        })
    return res


@router.get("/config")
def get_collector_config():
    """Returns authorized configuration for local collectors."""
    from shared.constants import (
        ALLOWED_EGRESS_FIELDS,
        RULE_THRESHOLDS,
        HEARTBEAT_INTERVAL_SECONDS,
    )
    return {
        "heartbeat_interval_seconds": HEARTBEAT_INTERVAL_SECONDS,
        "allowed_fields": ALLOWED_EGRESS_FIELDS,
        "rule_thresholds": RULE_THRESHOLDS,
    }
