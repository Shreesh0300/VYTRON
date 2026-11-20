"""
Backend Statistical Anomaly Detection Engine
Uses NumPy to compute rolling baseline means, standard deviations, and z-scores.
Identifies subtle performance degradation that static threshold rules miss.
"""
from datetime import datetime, timezone
import numpy as np
from sqlalchemy.orm import Session
from shared.constants import (
    STAT_MIN_SAMPLES,
    STAT_ROLLING_WINDOW,
    STAT_Z_SCORE_WARNING,
    STAT_Z_SCORE_CRITICAL,
)
from shared.schemas import generate_id
from backend.models.platform_models import Metric, Alert, AuditLog


def evaluate_statistical(
    server_id: str,
    metric_name: str,
    value: float,
    tenant_id: str,
    metric_id: int | None,
    db: Session,
) -> list[Alert]:
    """
    Computes rolling mean and std dev across recent samples.
    Triggers alerts when z-score deviates significantly from baseline.
    Requires minimum historical sample threshold to prevent false positives.
    """
    # Fetch recent historical records
    history = (
        db.query(Metric.metric_value)
        .filter(
            Metric.tenant_id == tenant_id,
            Metric.server_id == server_id,
            Metric.metric_name == metric_name,
        )
        .order_by(Metric.event_timestamp.desc())
        .limit(STAT_ROLLING_WINDOW)
        .all()
    )

    if len(history) < STAT_MIN_SAMPLES:
        return []

    values = [h[0] for h in history]
    mean = float(np.mean(values))
    std = float(np.std(values))

    # Guard against zero variance
    if std < 1e-4:
        return []

    z_score = abs(value - mean) / std
    alerts_created = []
    now_str = datetime.now(timezone.utc).isoformat()

    if z_score >= STAT_Z_SCORE_CRITICAL:
        alert = Alert(
            alert_id=generate_id("ALT-STAT"),
            tenant_id=tenant_id,
            server_id=server_id,
            metric_id=metric_id,
            detection_method="statistical",
            severity="critical",
            description=(
                f"Statistical critical anomaly: {metric_name} on {server_id} observed {value:.2f} "
                f"(baseline mean: {mean:.2f}, std: {std:.2f}, z-score: {z_score:.2f} >= {STAT_Z_SCORE_CRITICAL})"
            ),
            created_at=now_str,
            status="active",
        )
        db.add(alert)
        alerts_created.append(alert)
    elif z_score >= STAT_Z_SCORE_WARNING:
        alert = Alert(
            alert_id=generate_id("ALT-STAT"),
            tenant_id=tenant_id,
            server_id=server_id,
            metric_id=metric_id,
            detection_method="statistical",
            severity="warning",
            description=(
                f"Statistical warning deviation: {metric_name} on {server_id} observed {value:.2f} "
                f"(baseline mean: {mean:.2f}, std: {std:.2f}, z-score: {z_score:.2f} >= {STAT_Z_SCORE_WARNING})"
            ),
            created_at=now_str,
            status="active",
        )
        db.add(alert)
        alerts_created.append(alert)

    for a in alerts_created:
        audit = AuditLog(
            audit_id=generate_id("AUDIT"),
            tenant_id=tenant_id,
            actor="statistical_engine",
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
