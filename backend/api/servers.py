"""
Servers Inventory, Detailed Snapshot, Metrics Query, and Demo Control APIs
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import httpx
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.connection import get_db
from backend.models.platform_models import Server, Metric, Alert, Incident, IncidentAlert
from shared.constants import (
    DEFAULT_TENANT_ID,
    SERVER_PROFILES,
    SIMULATOR_URL,
    RULE_THRESHOLDS,
)

servers_router = APIRouter(prefix="/api/servers", tags=["Servers"])
metrics_router = APIRouter(prefix="/api/metrics", tags=["Metrics"])
demo_router = APIRouter(prefix="/api/demo", tags=["Demo Mode"])


# ── Pydantic Request Models ──────────────────────────────────────────────

class ServerControlRequest(BaseModel):
    action: str  # fail | recover | set_metric
    metric: Optional[str] = None
    value: Optional[float] = None


class DemoScenarioRequest(BaseModel):
    scenario: str
    server_id: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────

async def _fetch_simulator_server_info(server_id: str) -> dict[str, Any]:
    """Fetch live activity and dynamic logs directly from the simulator daemon."""
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{SIMULATOR_URL}/servers/{server_id}")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {}


async def _fetch_simulator_logs(server_id: str) -> list[dict[str, Any]]:
    """Fetch recent dynamic logs from simulator."""
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{SIMULATOR_URL}/servers/{server_id}/logs")
            if resp.status_code == 200:
                return resp.json().get("logs", [])
    except Exception:
        pass
    return []


# ── Servers Endpoints ────────────────────────────────────────────────────

@servers_router.get("")
async def list_servers(
    tenant_id: str = DEFAULT_TENANT_ID,
    db: Session = Depends(get_db),
):
    """
    Returns the comprehensive 10-server inventory with:
    - Server ID, Name, Role, Infrastructure Type
    - State (ONLINE, WARNING, CRITICAL, OFFLINE)
    - Telemetry Feed Vitality (ACTIVE, DELAYED, LOST)
    - Live snapshot of all 10 system metrics
    - Current operational activity
    """
    servers = db.query(Server).filter_by(tenant_id=tenant_id).all()
    now = datetime.now(timezone.utc)
    active_cutoff = (now - timedelta(seconds=20)).isoformat()
    delayed_cutoff = (now - timedelta(seconds=60)).isoformat()

    # Pre-fetch all simulator states in ONE single call
    sim_servers_map: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=0.8) as client:
            resp = await client.get(f"{SIMULATOR_URL}/servers")
            if resp.status_code == 200:
                sim_servers_map = resp.json().get("servers", {})
    except Exception:
        pass

    results = []
    for s in servers:
        profile = SERVER_PROFILES.get(s.server_id, {})
        role_label = profile.get("role", "Infrastructure Node")

        # Find latest metric timestamp
        latest_metric_row = (
            db.query(Metric)
            .filter_by(server_id=s.server_id, tenant_id=tenant_id)
            .order_by(Metric.event_timestamp.desc())
            .first()
        )

        last_seen_iso = latest_metric_row.event_timestamp if latest_metric_row else None

        # Determine Feed Vitality
        if not last_seen_iso:
            feed_status = "LOST"
        elif last_seen_iso >= active_cutoff:
            feed_status = "ACTIVE"
        elif last_seen_iso >= delayed_cutoff:
            feed_status = "DELAYED"
        else:
            feed_status = "LOST"

        # Check active alerts on this server
        crit_alerts = (
            db.query(Alert)
            .filter_by(server_id=s.server_id, tenant_id=tenant_id, status="active", severity="critical")
            .count()
        )
        warn_alerts = (
            db.query(Alert)
            .filter_by(server_id=s.server_id, tenant_id=tenant_id, status="active", severity="warning")
            .count()
        )

        # Get latest snapshot metrics
        recent_rows = (
            db.query(Metric)
            .filter_by(server_id=s.server_id, tenant_id=tenant_id)
            .order_by(Metric.event_timestamp.desc())
            .limit(25)
            .all()
        )

        metrics_snapshot: dict[str, float] = {}
        for r in recent_rows:
            if r.metric_name not in metrics_snapshot:
                metrics_snapshot[r.metric_name] = r.metric_value

        # Health state calculation
        avail = metrics_snapshot.get("service_availability", 1.0)
        cpu = metrics_snapshot.get("cpu_usage", 0.0)
        mem = metrics_snapshot.get("memory_usage", 0.0)
        disk = metrics_snapshot.get("disk_usage", 0.0)
        err = metrics_snapshot.get("error_rate", 0.0)

        if avail <= 0:
            health_state = "OFFLINE"
        elif crit_alerts > 0 or cpu >= 90 or mem >= 95 or disk >= 90 or err >= 15:
            health_state = "CRITICAL"
        elif warn_alerts > 0 or cpu >= 80 or mem >= 85 or disk >= 80 or err >= 5:
            health_state = "WARNING"
        else:
            health_state = "ONLINE"

        # Simulator live enrichment from single batched fetch
        sim_data = sim_servers_map.get(s.server_id, {})
        activity = sim_data.get("activity", f"Serving workload: {role_label}")
        uptime = sim_data.get("current", {}).get("uptime", 86400 * 5)

        results.append({
            "server_id": s.server_id,
            "tenant_id": s.tenant_id,
            "server_name": s.server_name,
            "server_type": s.server_type,
            "role": role_label,
            "status": health_state,
            "feed_status": feed_status,
            "last_metric_time": last_seen_iso,
            "active_critical_alerts": crit_alerts,
            "active_warning_alerts": warn_alerts,
            "activity": activity,
            "uptime": uptime,
            "snapshot": metrics_snapshot,
        })

    return results


@servers_router.get("/{server_id}/detail")
async def get_server_detail(
    server_id: str,
    tenant_id: str = DEFAULT_TENANT_ID,
    db: Session = Depends(get_db),
):
    """
    Returns full details for a single server:
    - Comprehensive snapshot of all 10 live metrics
    - Baselines & Role description
    - Active alerts and correlated incidents
    - Live dynamic server operational logs
    """
    sid = server_id.upper()
    server = db.query(Server).filter_by(server_id=sid, tenant_id=tenant_id).first()
    if not server:
        raise HTTPException(status_code=404, detail=f"Server {sid} not found")

    profile = SERVER_PROFILES.get(sid, {})
    role_label = profile.get("role", "Infrastructure Node")

    # Fetch live simulation data & logs
    sim_data = await _fetch_simulator_server_info(sid)
    logs = await _fetch_simulator_logs(sid)

    # Fetch active alerts
    alerts = (
        db.query(Alert)
        .filter_by(server_id=sid, tenant_id=tenant_id, status="active")
        .order_by(Alert.created_at.desc())
        .limit(10)
        .all()
    )

    # Fetch related incidents involving this server via IncidentAlert join
    incident_subquery = (
        db.query(IncidentAlert.incident_id)
        .join(Alert, IncidentAlert.alert_id == Alert.alert_id)
        .filter(Alert.server_id == sid)
        .subquery()
    )
    incidents = (
        db.query(Incident)
        .filter(
            Incident.tenant_id == tenant_id,
            Incident.incident_id.in_(incident_subquery),
            Incident.status.in_(["open", "investigating"]),
        )
        .order_by(Incident.created_at.desc())
        .limit(5)
        .all()
    )
    relevant_incidents = [
        {
            "incident_id": inc.incident_id,
            "title": inc.title,
            "severity": inc.severity,
            "status": inc.status,
            "created_at": inc.created_at,
        }
        for inc in incidents
    ]

    # Fetch latest metrics from DB
    recent_metrics = (
        db.query(Metric)
        .filter_by(server_id=sid, tenant_id=tenant_id)
        .order_by(Metric.event_timestamp.desc())
        .limit(30)
        .all()
    )

    metrics_snapshot: dict[str, float] = {}
    for r in recent_metrics:
        if r.metric_name not in metrics_snapshot:
            metrics_snapshot[r.metric_name] = r.metric_value

    # Merge with simulator metrics if available
    if sim_data and "current" in sim_data:
        for k, v in sim_data["current"].items():
            metrics_snapshot.setdefault(k, v)

    health_status = sim_data.get("status", "ONLINE") if sim_data else "ONLINE"
    activity = sim_data.get("activity", f"Serving {role_label}") if sim_data else f"Serving {role_label}"
    uptime = sim_data.get("current", {}).get("uptime", 86400 * 5) if sim_data else 86400 * 5

    return {
        "server_id": server.server_id,
        "server_name": server.server_name,
        "server_type": server.server_type,
        "role": role_label,
        "status": health_status,
        "activity": activity,
        "uptime": uptime,
        "metrics": metrics_snapshot,
        "baselines": sim_data.get("baselines", {}),
        "recent_logs": logs,
        "alerts": [
            {
                "alert_id": a.alert_id,
                "severity": a.severity,
                "detection_method": a.detection_method,
                "description": a.description,
                "created_at": a.created_at,
            }
            for a in alerts
        ],
        "incidents": relevant_incidents,
    }


@servers_router.post("/{server_id}/control")
async def control_server(
    server_id: str,
    req: ServerControlRequest,
):
    """Proxy interactive control commands to simulator daemon."""
    sid = server_id.upper()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{SIMULATOR_URL}/scenarios/server-action",
                json={
                    "server_id": sid,
                    "action": req.action,
                    "metric": req.metric,
                    "value": req.value,
                },
            )
            return resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Simulator daemon at {SIMULATOR_URL}: {str(exc)}",
        )


# ── Demo Mode Endpoints ──────────────────────────────────────────────────

@demo_router.get("/state")
async def get_demo_state():
    """Returns currently active demo scenario."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{SIMULATOR_URL}/scenarios/active")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"active_scenario": "Normal Operations", "simulator_online": False}


@demo_router.post("/scenario")
async def trigger_demo_scenario(req: DemoScenarioRequest):
    """Trigger one of the 8 predefined judge demo scenarios."""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(
                f"{SIMULATOR_URL}/scenarios/demo-scenario",
                json={"scenario": req.scenario, "server_id": req.server_id},
            )
            return resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Simulator daemon at {SIMULATOR_URL}: {str(exc)}",
        )


@demo_router.post("/reset")
async def reset_demo_scenario():
    """Reset all servers to baseline."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(f"{SIMULATOR_URL}/scenarios/reset")
            return resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Simulator daemon: {str(exc)}",
        )


# ── Metrics Query Endpoint ───────────────────────────────────────────────

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
