"""
Backend Recommendation Engine
Generates actionable remediation proposals linked to incidents.
Feeds the Assisted/Autonomous Ops workflow with simulated action execution and rollback.
"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from shared.schemas import generate_id, LLMAnalysisRequest, LLMAnalysisResponse
from backend.models.platform_models import Incident, Alert, IncidentAlert, Recommendation, AuditLog
from backend.services.llm_engine import get_llm_provider


async def generate_recommendations(incident: Incident, db: Session) -> list[Recommendation]:
    """
    Synthesizes alert evidence, queries LLM analysis provider,
    and records concrete recommendations with audit logging.
    """
    now_str = datetime.now(timezone.utc).isoformat()

    # Query linked alerts
    linked_alerts = (
        db.query(Alert)
        .join(IncidentAlert, IncidentAlert.alert_id == Alert.alert_id)
        .filter(IncidentAlert.incident_id == incident.incident_id)
        .all()
    )

    alert_dicts = [
        {
            "alert_id": a.alert_id,
            "server_id": a.server_id,
            "severity": a.severity,
            "method": a.detection_method,
            "description": a.description,
        }
        for a in linked_alerts
    ]

    llm_req = LLMAnalysisRequest(
        incident_id=incident.incident_id,
        alerts=alert_dicts,
        metrics_context=[],
        server_info={"title": incident.title, "severity": incident.severity},
    )

    provider = get_llm_provider()
    analysis: LLMAnalysisResponse = await provider.analyze(llm_req)

    recommendations_created = []

    # Format recommendations from analysis steps
    for idx, step in enumerate(analysis.recommended_steps):
        rec_id = generate_id("REC")
        rec = Recommendation(
            recommendation_id=rec_id,
            incident_id=incident.incident_id,
            explanation=f"{analysis.summary} (Factor: {analysis.contributing_factors[0] if analysis.contributing_factors else 'Anomaly'})",
            recommended_action=step,
            llm_generated=True,
            approval_status="pending",
            created_at=now_str,
        )
        db.add(rec)
        recommendations_created.append(rec)

        audit = AuditLog(
            audit_id=generate_id("AUDIT"),
            tenant_id=incident.tenant_id,
            actor="aiops_recommendation_engine",
            action="recommendation_generated",
            resource_type="recommendation",
            resource_id=rec_id,
            timestamp=now_str,
            details=f"Proposed remediation for {incident.incident_id}: {step}",
        )
        db.add(audit)

    db.commit()
    return recommendations_created
