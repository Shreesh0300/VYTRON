"""
Backend Rule-Based Detection Engine
Evaluates telemetry against configured operational thresholds.
"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from shared.constants import RULE_THRESHOLDS
from shared.schemas import generate_id
from backend.models.platform_models import Alert, AuditLog


def evaluate_rules(
    server_id: str,
    metric_name: str,
    value: float,
    tenant_id: str,
    metric_id: int | None,
    db: Session,
) -> list[Alert]:
    """
    Checks incoming metric value against static rules.
    Creates and records Alert and Audit entries if thresholds are breached.
    """
    thresholds = RULE_THRESHOLDS.get(metric_name)
    if not thresholds:
        return []

    alerts_created = []
    now_str = datetime.now(timezone.utc).isoformat()

    # Rule: Service Availability
    if metric_name == "service_availability" and value <= 0:
        alert = Alert(
            alert_id=generate_id("ALT-RULE"),
            tenant_id=tenant_id,
            server_id=server_id,
            metric_id=metric_id,
            detection_method="rule",
            severity="critical",
            description=f"Service outage detected on {server_id} (availability: {value})",
            created_at=now_str,
            status="active",
        )
        db.add(alert)
        alerts_created.append(alert)

    # Standard warning and critical thresholds
    crit = thresholds.get("critical")
    warn = thresholds.get("warning")

    if crit is not None and value >= crit:
        alert = Alert(
            alert_id=generate_id("ALT-RULE"),
            tenant_id=tenant_id,
            server_id=server_id,
            metric_id=metric_id,
            detection_method="rule",
            severity="critical",
            description=f"Critical breach: {metric_name} on {server_id} is {value:.2f} (threshold: {crit})",
            created_at=now_str,
            status="active",
        )
        db.add(alert)
        alerts_created.append(alert)
    elif warn is not None and value >= warn:
        alert = Alert(
            alert_id=generate_id("ALT-RULE"),
            tenant_id=tenant_id,
            server_id=server_id,
            metric_id=metric_id,
            detection_method="rule",
            severity="warning",
            description=f"Warning breach: {metric_name} on {server_id} is {value:.2f} (threshold: {warn})",
            created_at=now_str,
            status="active",
        )
        db.add(alert)
        alerts_created.append(alert)

    for a in alerts_created:
        audit = AuditLog(
            audit_id=generate_id("AUDIT"),
            tenant_id=tenant_id,
            actor="rules_engine",
            action="alert_created",
            resource_type="alert",
            resource_id=a.alert_id,
            timestamp=now_str,
            details=a.description,
        )
        db.add(audit)

    if alerts_created:
        db.commit()

    return alerts_created
