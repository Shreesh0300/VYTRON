"""
Recommendations and Remediation APIs (Assisted → Autonomous Ops Simulation)
Supports human approval, simulated action execution, and rollback.
Logs complete audit trail for every action.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from shared.schemas import (
    RemediationApproval,
    RemediationExecution,
    RemediationRollback,
    generate_id,
)
from backend.database.connection import get_db
from backend.models.platform_models import Recommendation, AuditLog
from shared.constants import DEFAULT_TENANT_ID

rec_router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])
remediation_router = APIRouter(prefix="/api/remediation", tags=["Remediation"])


@rec_router.get("")
def list_recommendations(
    incident_id: str | None = None,
    approval_status: str | None = None,
    db: Session = Depends(get_db),
):
    """Queries operational recommendations."""
    q = db.query(Recommendation)
    if incident_id:
        q = q.filter(Recommendation.incident_id == incident_id)
    if approval_status:
        q = q.filter(Recommendation.approval_status == approval_status)

    recs = q.order_by(Recommendation.created_at.desc()).all()
    return [
        {
            "recommendation_id": r.recommendation_id,
            "incident_id": r.incident_id,
            "explanation": r.explanation,
            "recommended_action": r.recommended_action,
            "llm_generated": r.llm_generated,
            "approval_status": r.approval_status,
            "created_at": r.created_at,
        }
        for r in recs
    ]


@remediation_router.post("/approve")
def approve_remediation(req: RemediationApproval, db: Session = Depends(get_db)):
    """Operator approval of an AIOps recommendation."""
    rec = db.query(Recommendation).filter_by(recommendation_id=req.recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.approval_status = "approved"
    now_str = datetime.now(timezone.utc).isoformat()

    audit = AuditLog(
        audit_id=generate_id("AUDIT"),
        tenant_id=DEFAULT_TENANT_ID,
        actor=req.approved_by,
        action="remediation_approved",
        resource_type="recommendation",
        resource_id=rec.recommendation_id,
        timestamp=now_str,
        details=f"Operator approved action: {rec.recommended_action}",
    )
    db.add(audit)
    db.commit()
    return {"status": "approved", "recommendation_id": rec.recommendation_id}


@remediation_router.post("/execute")
def execute_remediation(req: RemediationExecution, db: Session = Depends(get_db)):
    """Executes a safe simulation of the approved operational action."""
    rec = db.query(Recommendation).filter_by(recommendation_id=req.recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if rec.approval_status != "approved":
        raise HTTPException(status_code=400, detail="Action must be approved before execution")

    rec.approval_status = "executed"
    now_str = datetime.now(timezone.utc).isoformat()

    audit = AuditLog(
        audit_id=generate_id("AUDIT"),
        tenant_id=DEFAULT_TENANT_ID,
        actor=req.executed_by,
        action="remediation_executed",
        resource_type="remediation_simulation",
        resource_id=rec.recommendation_id,
        timestamp=now_str,
        details=f"SIMULATED EXECUTION of action: {rec.recommended_action}. Target simulated successfully.",
    )
    db.add(audit)
    db.commit()
    return {
        "status": "executed",
        "simulation": True,
        "recommendation_id": rec.recommendation_id,
        "message": f"Simulated execution succeeded: {rec.recommended_action}",
    }


@remediation_router.post("/rollback")
def rollback_remediation(req: RemediationRollback, db: Session = Depends(get_db)):
    """Rollback execution of simulated remediation."""
    rec = db.query(Recommendation).filter_by(recommendation_id=req.recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.approval_status = "rolled_back"
    now_str = datetime.now(timezone.utc).isoformat()

    audit = AuditLog(
        audit_id=generate_id("AUDIT"),
        tenant_id=DEFAULT_TENANT_ID,
        actor=req.rolled_back_by,
        action="remediation_rolled_back",
        resource_type="remediation_simulation",
        resource_id=rec.recommendation_id,
        timestamp=now_str,
        details=f"SIMULATED ROLLBACK of action {rec.recommended_action}. Reason: {req.reason}",
    )
    db.add(audit)
    db.commit()
    return {
        "status": "rolled_back",
        "recommendation_id": rec.recommendation_id,
        "message": "Action successfully rolled back in simulation environment.",
    }
