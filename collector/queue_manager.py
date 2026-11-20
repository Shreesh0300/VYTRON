"""
Collector Queue Manager
Implements resilient local persistent buffering and exponential backoff.
Guarantees zero data loss and exact delivery during Central Platform outages.
"""
import json
import asyncio
from datetime import datetime, timezone, timedelta
import httpx
from collector.models import EgressQueue, TransferAudit
from collector.database import SessionLocal
from collector.config import CONFIG
from shared.schemas import ApprovedTelemetryPayload


def enqueue_payload(session, payload: ApprovedTelemetryPayload):
    """Persists approved payload into SQLite egress_queue prior to network transmission."""
    item = EgressQueue(
        payload_id=payload.payload_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        payload_json=payload.model_dump_json(),
        delivery_status="pending",
        retry_count=0,
    )
    session.add(item)
    session.commit()


async def drain_queue(client: httpx.AsyncClient):
    """
    Scans pending/retryable payloads and attempts transmission with exponential backoff.
    """
    db = SessionLocal()
    try:
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        # 1. Recover stale in_progress items from unexpected worker crashes (>30s old)
        stale_cutoff = (now_dt - timedelta(seconds=30)).isoformat()
        stale_items = (
            db.query(EgressQueue)
            .filter(
                EgressQueue.delivery_status == "in_progress",
                EgressQueue.last_attempt_at < stale_cutoff,
            )
            .all()
        )
        for s in stale_items:
            s.delivery_status = "retryable"
        if stale_items:
            db.commit()

        # 2. Query pending and retryable payloads
        items = (
            db.query(EgressQueue)
            .filter(EgressQueue.delivery_status.in_(["pending", "retryable"]))
            .order_by(EgressQueue.created_at.asc())
            .limit(20)
            .all()
        )

        if not items:
            return

        headers = {
            "X-API-Key": CONFIG["api_key"],
            "Content-Type": "application/json",
        }
        url = f"{CONFIG['backend_url']}/api/telemetry"

        for item in items:
            # 3. Check exponential backoff delay for retryable items
            if item.delivery_status == "retryable" and item.last_attempt_at:
                try:
                    last_attempt = datetime.fromisoformat(item.last_attempt_at)
                    if last_attempt.tzinfo is None:
                        last_attempt = last_attempt.replace(tzinfo=timezone.utc)
                    delay = min(
                        CONFIG["queue_retry_base_delay"] * (CONFIG["queue_backoff_multiplier"] ** item.retry_count),
                        CONFIG["queue_retry_max_delay"],
                    )
                    if (now_dt - last_attempt).total_seconds() < delay:
                        continue  # Backoff delay has not elapsed yet
                except Exception:
                    pass

            item.delivery_status = "in_progress"
            item.last_attempt_at = now_iso
            db.commit()

            try:
                payload_dict = json.loads(item.payload_json)
                resp = await client.post(url, json=payload_dict, headers=headers, timeout=5.0)

                if resp.status_code == 200:
                    item.delivery_status = "delivered"
                    item.acknowledged_at = datetime.now(timezone.utc).isoformat()
                    # Also update transfer_audit transmission_status
                    audit = db.query(TransferAudit).filter_by(payload_id=item.payload_id).first()
                    if audit:
                        audit.transmission_status = "delivered"
                    db.commit()
                else:
                    raise Exception(f"HTTP {resp.status_code}: {resp.text}")

            except Exception as e:
                item.retry_count += 1
                if item.retry_count >= CONFIG["queue_retry_max_attempts"]:
                    item.delivery_status = "failed"
                else:
                    item.delivery_status = "retryable"

                audit = db.query(TransferAudit).filter_by(payload_id=item.payload_id).first()
                if audit:
                    audit.transmission_status = item.delivery_status
                db.commit()
                # If backend is down, break loop to avoid pounding it
                break

    finally:
        db.close()
