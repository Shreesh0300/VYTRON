"""
Collector Egress Module
Records every payload that leaves the collector in transfer_audit.
Provides query capabilities for the Egress Proof Panel.
"""
import json
from collector.models import TransferAudit
from shared.schemas import EgressRecord


def record_egress(session, egress_record: EgressRecord):
    """Stores the EgressRecord into collector.db transfer_audit."""
    entry = TransferAudit(
        audit_id=egress_record.audit_id,
        payload_id=egress_record.payload_id,
        policy_result=egress_record.policy_result,
        approved_fields=json.dumps(egress_record.approved_fields),
        blocked_fields=json.dumps(egress_record.blocked_fields),
        transmission_status=egress_record.transmission_status,
        timestamp=egress_record.timestamp.isoformat(),
    )
    session.add(entry)
    session.commit()


def get_egress_history(session, limit: int = 50) -> list[dict]:
    """Retrieves recent egress events."""
    rows = session.query(TransferAudit).order_by(TransferAudit.timestamp.desc()).limit(limit).all()
    results = []
    for r in rows:
        results.append({
            "audit_id": r.audit_id,
            "payload_id": r.payload_id,
            "policy_result": r.policy_result,
            "approved_fields": json.loads(r.approved_fields) if r.approved_fields else [],
            "blocked_fields": json.loads(r.blocked_fields) if r.blocked_fields else [],
            "transmission_status": r.transmission_status,
            "timestamp": r.timestamp,
        })
    return results
