"""
Collector Health Monitor
Tracks local host CPU, memory, version, and sends heartbeats to central backend.
"""
import psutil
from datetime import datetime, timezone
import httpx
from shared.schemas import CollectorHeartbeat, CollectorConfigStatus
from collector.config import CONFIG
from collector.database import SessionLocal
from collector.models import SourceRegistry, CollectorHealth


def get_health() -> CollectorHeartbeat:
    """Collects system stats using psutil."""
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory().percent

    db = SessionLocal()
    try:
        source_count = db.query(SourceRegistry).count()
        # Update local collector_health table
        ch = db.query(CollectorHealth).filter_by(collector_id=CONFIG["collector_id"]).first()
        now_str = datetime.now(timezone.utc).isoformat()
        if not ch:
            ch = CollectorHealth(
                collector_id=CONFIG["collector_id"],
                heartbeat_timestamp=now_str,
                cpu_usage=cpu,
                memory_usage=mem,
                software_version="1.0.0",
                configuration_status="configured",
            )
            db.add(ch)
        else:
            ch.heartbeat_timestamp = now_str
            ch.cpu_usage = cpu
            ch.memory_usage = mem
        db.commit()
    finally:
        db.close()

    return CollectorHeartbeat(
        collector_id=CONFIG["collector_id"],
        tenant_id=CONFIG["tenant_id"],
        timestamp=datetime.now(timezone.utc),
        cpu_usage=cpu,
        memory_usage=mem,
        software_version="1.0.0",
        configuration_status=CollectorConfigStatus.CONFIGURED,
        source_count=source_count,
    )


async def send_heartbeat(client: httpx.AsyncClient) -> bool:
    """Transmits heartbeat to Central SaaS backend."""
    hb = get_health()
    url = f"{CONFIG['backend_url']}/api/collectors/heartbeat"
    headers = {
        "X-API-Key": CONFIG["api_key"],
        "Content-Type": "application/json",
    }
    try:
        resp = await client.post(url, json=hb.model_dump(mode="json"), headers=headers, timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False
