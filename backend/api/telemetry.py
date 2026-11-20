"""
Telemetry Ingestion API Router
Enforces payload idempotency via payload_id uniqueness constraint.
Applies tenant scoping.
Runs rule and statistical anomaly detection pipelines.
Triggers event correlation and LLM recommendation generation.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from shared.schemas import ApprovedTelemetryPayload, TelemetryAck
from backend.database.connection import get_db
from backend.security.auth import verify_collector_api_key
from backend.models.platform_models import Metric, Server, Collector
from backend.services.rules_engine import evaluate_rules
from backend.services.statistical_engine import evaluate_statistical
from backend.services.correlation_engine import correlate_alerts
from backend.services.recommendation_engine import generate_recommendations

router = APIRouter(prefix="/api", tags=["Telemetry"])


@router.post("/telemetry", response_model=TelemetryAck)
async def receive_telemetry(
    payload: ApprovedTelemetryPayload,
    tenant_id: str = Depends(verify_collector_api_key),
    db: Session = Depends(get_db),
):
    """
    Ingests allow-listed telemetry metadata.
    Idempotent: Duplicate payload_id returns positive ACK without double-processing.
    """
    now_str = datetime.now(timezone.utc).isoformat()

    # 1. Check idempotency: does payload_id already exist?
    existing = db.query(Metric).filter_by(payload_id=payload.payload_id).first()
    if existing:
        return TelemetryAck(
            payload_id=payload.payload_id,
            accepted=True,
            message="Duplicate payload recognized and safely acknowledged (idempotent)",
        )

    # 2. Update server last seen / status
    server = db.query(Server).filter_by(server_id=payload.source_id).first()
    if server:
        # Check if severity requires updating status
        if payload.severity.value == "critical":
            server.status = "poor"
        elif payload.severity.value == "warning" and server.status not in ["poor"]:
            server.status = "fair"
        elif server.status in ["poor", "fair"] and payload.value > 0 and payload.metric == "service_availability":
            server.status = "good"

    # 3. Store metric
    metric_record = Metric(
        tenant_id=tenant_id,
        server_id=payload.source_id,
        payload_id=payload.payload_id,
        metric_name=payload.metric,
        metric_value=payload.value,
        event_timestamp=payload.timestamp.isoformat(),
        received_timestamp=now_str,
    )
    db.add(metric_record)
    try:
        db.commit()
        db.refresh(metric_record)
    except IntegrityError:
        db.rollback()
        return TelemetryAck(
            payload_id=payload.payload_id,
            accepted=True,
            message="Concurrent duplicate payload_id handled idempotently",
        )

    # 4. Run Detection Pipeline
    created_alerts = []
    # A. Rule-based evaluation
    rule_alerts = evaluate_rules(
        server_id=payload.source_id,
        metric_name=payload.metric,
        value=payload.value,
        tenant_id=tenant_id,
        metric_id=metric_record.metric_id,
        db=db,
    )
    created_alerts.extend(rule_alerts)

    # B. Statistical baseline evaluation (NumPy)
    stat_alerts = evaluate_statistical(
        server_id=payload.source_id,
        metric_name=payload.metric,
        value=payload.value,
        tenant_id=tenant_id,
        metric_id=metric_record.metric_id,
        db=db,
    )
    created_alerts.extend(stat_alerts)

    # 5. Run Correlation Engine
    if created_alerts:
        incidents = correlate_alerts(created_alerts, tenant_id=tenant_id, db=db)
        # 6. Generate Recommendations for newly correlated incidents
        for inc in incidents:
            await generate_recommendations(inc, db)

    return TelemetryAck(
        payload_id=payload.payload_id,
        accepted=True,
        message="Telemetry ingested and analyzed successfully",
    )
