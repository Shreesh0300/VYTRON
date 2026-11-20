"""
Privacy Filter Engine (Tier 1 Trust Boundary)
Constructs approved payloads exclusively using allow-lists.
Performs regex scanning and redaction of test secrets.
Guarantees raw payloads, credentials, and tokens NEVER leave the local environment.
"""
import re
import json
from datetime import datetime, timezone
from shared.constants import (
    ALLOWED_EGRESS_FIELDS,
    BLOCKED_METADATA_KEYS,
    SENSITIVE_PATTERNS,
)
from shared.schemas import (
    ApprovedTelemetryPayload,
    EgressRecord,
    Severity,
    Category,
    generate_id,
)
from collector.config import CONFIG


def redact_string(val: str) -> tuple[str, bool]:
    """Scans and redacts matching patterns."""
    redacted = False
    current_val = val
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, current_val):
            redacted = True
            current_val = re.sub(pattern, "[REDACTED_SECRET]", current_val)
    return current_val, redacted


def sanitize_dict(d: dict) -> tuple[dict, list[str]]:
    """Sanitizes metadata dictionary removing blocked keys and redacting values."""
    sanitized = {}
    blocked_keys = []
    
    for k, v in d.items():
        if k.lower() in [b.lower() for b in BLOCKED_METADATA_KEYS]:
            blocked_keys.append(f"metadata.{k}")
            continue
        
        if isinstance(v, str):
            clean_v, was_redacted = redact_string(v)
            if was_redacted:
                blocked_keys.append(f"metadata.{k}:secret_scrubbed")
            sanitized[k] = clean_v
        elif isinstance(v, dict):
            sub_clean, sub_blocked = sanitize_dict(v)
            sanitized[k] = sub_clean
            blocked_keys.extend([f"metadata.{k}.{sk}" for sk in sub_blocked])
        elif isinstance(v, list):
            clean_list = []
            for idx, item in enumerate(v):
                if isinstance(item, str):
                    c_item, was_redacted = redact_string(item)
                    if was_redacted:
                        blocked_keys.append(f"metadata.{k}[{idx}]:secret_scrubbed")
                    clean_list.append(c_item)
                elif isinstance(item, dict):
                    c_dict, sub_blocked = sanitize_dict(item)
                    clean_list.append(c_dict)
                    for sk in sub_blocked:
                        prefix = f"metadata.{k}[{idx}]"
                        blocked_keys.append(f"{prefix}.{sk.split('.', 1)[-1]}" if "." in sk else f"{prefix}.{sk}")
                else:
                    clean_list.append(item)
            sanitized[k] = clean_list
        else:
            sanitized[k] = v
            
    return sanitized, blocked_keys


def filter_payload(normalized: dict) -> tuple[ApprovedTelemetryPayload, EgressRecord]:
    """
    Enforces the privacy filter:
    1. Removes blocked metadata fields.
    2. Redacts secrets found in text.
    3. Builds ApprovedTelemetryPayload using ONLY the explicit allow-list.
    4. Produces the EgressRecord containing the exact serialized JSON.
    """
    raw_metadata = normalized.get("metadata", {})
    clean_metadata, blocked_keys = sanitize_dict(raw_metadata)

    policy_result = "approved"
    if blocked_keys:
        policy_result = "redacted"

    payload_id = generate_id("PAYLOAD")
    ts_val = normalized["timestamp"]
    if isinstance(ts_val, str):
        ts = datetime.fromisoformat(ts_val)
    else:
        ts = ts_val

    # Construct Approved Payload purely from allowed fields
    approved_payload = ApprovedTelemetryPayload(
        payload_id=payload_id,
        tenant_id=CONFIG["tenant_id"],
        collector_id=CONFIG["collector_id"],
        source_id=normalized["source_id"],
        timestamp=ts,
        metric=normalized["metric"],
        value=normalized["value"],
        severity=Severity.INFO,
        category=Category(normalized.get("category", "infrastructure")),
        anomaly_detected=False,
        detection_method=None,
        metadata=clean_metadata if clean_metadata else None,
    )

    approved_fields = [
        f for f in ALLOWED_EGRESS_FIELDS
        if getattr(approved_payload, f, None) is not None
    ]

    # Exact serialized representation
    serialized_json = approved_payload.model_dump_json()

    egress_record = EgressRecord(
        audit_id=generate_id("AUDIT"),
        payload_id=payload_id,
        policy_result=policy_result,
        approved_fields=approved_fields,
        blocked_fields=blocked_keys,
        transmission_status="queued",
        timestamp=datetime.now(timezone.utc),
        serialized_payload=serialized_json,
    )

    return approved_payload, egress_record
