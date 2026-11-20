"""
Egress and Audit Logs API Routers
Provides visibility into exact transferred payloads, privacy redaction decisions, and audit history.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import httpx

from backend.database.connection import get_db
from backend.models.platform_models import AuditLog, Metric
from shared.constants import DEFAULT_TENANT_ID, COLLECTOR_URL

egress_router = APIRouter(prefix="/api/egress", tags=["Egress Proof"])
audit_router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs"])


@egress_router.get("")
async def get_egress_records(limit: int = 50):
    """
    Proxies to collector's /egress endpoint to retrieve the Egress Proof log:
    Exact serialized payload, approved fields, and scrubbed secrets.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{COLLECTOR_URL}/egress?limit={limit}")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return []


@audit_router.get("")
def query_audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    limit: int = Query(default=100, le=500),
    tenant_id: str = DEFAULT_TENANT_ID,
    db: Session = Depends(get_db),
):
    """Returns system audit trail."""
    q = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)

    logs = q.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "audit_id": l.audit_id,
            "tenant_id": l.tenant_id,
            "actor": l.actor,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "timestamp": l.timestamp,
            "details": l.details,
        }
        for l in logs
    ]
