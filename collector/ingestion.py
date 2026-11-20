"""
Collector Ingestion Router
Receives raw telemetry events from local sources / simulator.
Executes the ingestion pipeline:
1. Validates schema
2. Registers source
3. Stores raw event locally in local_events
4. Normalizes timestamp and fields
5. Applies privacy filter and redacts secrets
6. Evaluates local anomalies
7. Records egress proof in transfer_audit
8. Enqueues payload into persistent queue
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from shared.schemas import RawTelemetryEvent, generate_id
from collector.database import get_db
from collector.models import SourceRegistry, LocalEvent
from collector.normalization import normalize_event
from collector.privacy_filter import filter_payload
from collector.anomaly_detector import detect_local_anomalies
from collector.egress import record_egress
from collector.queue_manager import enqueue_payload

router = APIRouter()


@router.post("/telemetry")
async def ingest_telemetry(event: RawTelemetryEvent, db: Session = Depends(get_db)):
    """
    Local ingest endpoint for infrastructure telemetry.
    """
    event_id = generate_id("EVT")
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Update source registry
    source = db.query(SourceRegistry).filter_by(source_id=event.source_id).first()
    if not source:
        source = SourceRegistry(
            source_id=event.source_id,
            source_name=event.source_id,
            source_type=event.category.value if hasattr(event.category, "value") else str(event.category),
            configuration_status="active",
            last_seen=now_iso,
        )
        db.add(source)
    else:
        source.last_seen = now_iso
    db.commit()

    # 2. Store raw unredacted record in local_events table for local forensics
    raw_record = LocalEvent(
        event_id=event_id,
        source_id=event.source_id,
        event_timestamp=event.timestamp.isoformat(),
        event_type=event.event_type,
        event_data=event.model_dump_json(),
        processing_status="received",
    )
    db.add(raw_record)
    db.commit()

    # 3. Normalize
    normalized = normalize_event(event)

    # 4. Privacy Filter (constructs approved metadata, redacting secrets)
    approved_payload, egress_record = filter_payload(normalized)

    # 5. Local edge anomaly detection
    has_anomaly, sev, method, desc = detect_local_anomalies(
        event.source_id,
        event.metric,
        event.value,
        event.category.value if hasattr(event.category, "value") else str(event.category)
    )
    if has_anomaly:
        approved_payload.anomaly_detected = True
        approved_payload.severity = sev
        approved_payload.detection_method = method
        if approved_payload.metadata is None:
            approved_payload.metadata = {}
        approved_payload.metadata["local_alert_desc"] = desc
        # Re-sync serialized payload representation for egress proof
        egress_record.serialized_payload = approved_payload.model_dump_json()

    # 6. Record Egress Proof
    record_egress(db, egress_record)

    # 7. Persist to reliable egress_queue
    enqueue_payload(db, approved_payload)

    raw_record.processing_status = "queued_for_egress"
    db.commit()

    return {
        "status": "success",
        "event_id": event_id,
        "payload_id": approved_payload.payload_id,
        "policy_result": egress_record.policy_result,
        "redacted_fields": egress_record.blocked_fields,
    }
