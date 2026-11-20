"""
Normalization Module
Normalizes incoming raw telemetry into standard UTC format and metadata schemas.
"""
from datetime import datetime, timezone
from shared.schemas import RawTelemetryEvent


def normalize_event(raw: RawTelemetryEvent) -> dict:
    """
    Normalizes timestamps to standard ISO UTC format and ensures consistent keys.
    """
    ts = raw.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)

    return {
        "source_id": raw.source_id,
        "timestamp": ts.isoformat(),
        "metric": raw.metric,
        "value": float(raw.value),
        "category": raw.category.value if hasattr(raw.category, "value") else str(raw.category),
        "event_type": raw.event_type,
        "metadata": dict(raw.metadata or {}),
    }
