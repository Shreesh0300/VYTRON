"""
Servers Inventory and Metrics Query API Routers
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.platform_models import Server, Metric, Alert
from shared.constants import DEFAULT_TENANT_ID

servers_router = APIRouter(prefix="/api/servers", tags=["Servers"])
metrics_router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


@servers_router.get("")
def list_servers(
    tenant_id: str = DEFAULT_TENANT_ID,
    db: Session = Depends(get_db),
):
    """
    Returns server inventory with four-state health classification (Excellent, Good, Fair, Poor).
    Handles stale data by downgrading health state if no recent telemetry has been received.
    """
    servers = db.query(Server).filter_by(tenant_id=tenant_id).all()
    now = datetime.now(timezone.utc)
    stale_cutoff = (now - timedelta(seconds=60)).isoformat()

    results = []
    for s in servers:
        # Check last metric received for staleness
        latest_metric = (
            db.query(Metric)
            .filter_by(server_id=s.server_id, tenant_id=tenant_id)
            .order_by(Metric.event_timestamp.desc())
            .first()
        )

        health = s.status
        is_stale = False
        if not latest_metric:
            health = "poor"
            is_stale = True
        else:
            if latest_metric.event_timestamp < stale_cutoff:
                health = "fair"  # Downgrade on stale data
                is_stale = True

        # Check for active critical alerts
        active_crit = (
            db.query(Alert)
            .filter_by(server_id=s.server_id, tenant_id=tenant_id, status="active", severity="critical")
            .count()
        )
        if active_crit > 0:
            health = "poor"

        results.append({
            "server_id": s.server_id,
            "tenant_id": s.tenant_id,
            "server_name": s.server_name,
            "server_type": s.server_type,
            "status": health,
            "is_stale": is_stale,
            "last_metric_time": latest_metric.event_timestamp if latest_metric else None,
        })
    return results


@metrics_router.get("")
def query_metrics(
    server_id: str | None = None,
    metric: str | None = None,
    limit: int = Query(default=100, le=500),
    tenant_id: str = DEFAULT_TENANT_ID,
    db: Session = Depends(get_db),
):
    """
    Queries historical time-series metrics with filtering.
    """
    q = db.query(Metric).filter(Metric.tenant_id == tenant_id)
    if server_id:
        q = q.filter(Metric.server_id == server_id)
    if metric:
        q = q.filter(Metric.metric_name == metric)

    rows = q.order_by(Metric.event_timestamp.desc()).limit(limit).all()
    return [
        {
            "metric_id": r.metric_id,
            "server_id": r.server_id,
            "payload_id": r.payload_id,
            "metric_name": r.metric_name,
            "metric_value": r.metric_value,
            "event_timestamp": r.event_timestamp,
            "received_timestamp": r.received_timestamp,
        }
        for r in rows
    ]
