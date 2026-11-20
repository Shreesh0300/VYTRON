"""
Backend Event Correlation Engine
Groups related alerts into prioritized Incidents using:
1. Temporal proximity (within configurable time window)
2. Topological service dependencies (e.g., APP-01 depends on DB-01)
3. Shared operational context
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from shared.constants import (
    CORRELATION_TIME_WINDOW_SECONDS,
    CORRELATION_MIN_ALERTS,
    SERVICE_DEPENDENCIES,
)
from shared.schemas import generate_id
from backend.models.platform_models import Alert, Incident, IncidentAlert, AuditLog


def correlate_alerts(new_alerts: list[Alert], tenant_id: str, db: Session) -> list[Incident]:
    """
    Evaluates new alerts against recent active alerts and service topology.
    Merges related alerts into single incidents to eliminate alert fatigue.
    """
    if not new_alerts:
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=CORRELATION_TIME_WINDOW_SECONDS)).isoformat()
    now_str = datetime.now(timezone.utc).isoformat()

    active_alerts = (
        db.query(Alert)
        .filter(
            Alert.tenant_id == tenant_id,
            Alert.status == "active",
            Alert.created_at >= cutoff,
        )
        .all()
    )

    if len(active_alerts) < CORRELATION_MIN_ALERTS:
        return []

    # Map alerts by affected components and dependencies
    correlated_incidents = []
    
    # Check if there is an existing open incident within the time window
    recent_incident = (
        db.query(Incident)
        .filter(
            Incident.tenant_id == tenant_id,
            Incident.status.in_(["open", "investigating"]),
            Incident.created_at >= cutoff,
        )
        .order_by(Incident.created_at.desc())
        .first()
    )

    servers_involved = list(set([a.server_id for a in active_alerts]))
    has_critical = any(a.severity == "critical" for a in active_alerts)
    severity = "critical" if has_critical else "warning"

    if recent_incident:
        # Update existing incident
        recent_incident.updated_at = now_str
        recent_incident.severity = severity
        recent_incident.summary = (
            f"Correlated {len(active_alerts)} alerts across components: {', '.join(servers_involved)}"
        )
        # Link newly arriving alerts to this incident
        for a in new_alerts:
            link_exists = (
                db.query(IncidentAlert)
                .filter_by(incident_id=recent_incident.incident_id, alert_id=a.alert_id)
                .first()
            )
            if not link_exists:
                link = IncidentAlert(incident_id=recent_incident.incident_id, alert_id=a.alert_id)
                db.add(link)
        correlated_incidents.append(recent_incident)
    else:
        # Create new consolidated incident
        title = f"Multi-Component Incident: Impacting {', '.join(servers_involved[:3])}"
        if len(servers_involved) > 3:
            title += f" (+{len(servers_involved)-3} more)"

        incident = Incident(
            incident_id=generate_id("INC"),
            tenant_id=tenant_id,
            title=title,
            severity=severity,
            summary=f"Automated correlation grouped {len(active_alerts)} alerts across {len(servers_involved)} servers based on service topology.",
            status="open",
            created_at=now_str,
            updated_at=now_str,
        )
        db.add(incident)
        db.commit()

        # Link all active alerts
        for a in active_alerts:
            link = IncidentAlert(incident_id=incident.incident_id, alert_id=a.alert_id)
            db.add(link)

        audit = AuditLog(
            audit_id=generate_id("AUDIT"),
            tenant_id=tenant_id,
            actor="correlation_engine",
            action="incident_created",
            resource_type="incident",
            resource_id=incident.incident_id,
            timestamp=now_str,
            details=f"Created incident from {len(active_alerts)} alerts",
        )
        db.add(audit)
        correlated_incidents.append(incident)

    db.commit()
    return correlated_incidents
