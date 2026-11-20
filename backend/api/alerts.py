"""
Alerts, Incidents, and AIOps Insights API Routers
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.models.platform_models import Alert, Incident, IncidentAlert, Recommendation
from shared.constants import DEFAULT_TENANT_ID

alerts_router = APIRouter(prefix="/api/alerts", tags=["Alerts"])
incidents_router = APIRouter(prefix="/api/incidents", tags=["Incidents"])
aiops_router = APIRouter(prefix="/api/aiops", tags=["AIOps Insights"])


@alerts_router.get("")
def list_alerts(
    severity: str | None = None,
    status: str | None = None,
    server_id: str | None = None,
    limit: int = Query(default=100, le=500),
    tenant_id: str = DEFAULT_TENANT_ID,
    db: Session = Depends(get_db),
):
    """Lists alerts with filtering."""
    q = db.query(Alert).filter(Alert.tenant_id == tenant_id)
    if severity:
        q = q.filter(Alert.severity == severity)
    if status:
        q = q.filter(Alert.status == status)
    if server_id:
        q = q.filter(Alert.server_id == server_id)

    alerts = q.order_by(Alert.created_at.desc()).limit(limit).all()
    return [
        {
            "alert_id": a.alert_id,
            "tenant_id": a.tenant_id,
            "server_id": a.server_id,
            "metric_id": a.metric_id,
            "detection_method": a.detection_method,
            "severity": a.severity,
            "description": a.description,
            "created_at": a.created_at,
            "status": a.status,
        }
        for a in alerts
    ]


@incidents_router.get("")
def list_incidents(
    status: str | None = None,
    tenant_id: str = DEFAULT_TENANT_ID,
    db: Session = Depends(get_db),
):
    """Lists correlated incidents with their linked alerts."""
    q = db.query(Incident).filter(Incident.tenant_id == tenant_id)
    if status:
        q = q.filter(Incident.status == status)

    incidents = q.order_by(Incident.created_at.desc()).all()
    results = []
    for inc in incidents:
        linked_alert_ids = [
            row[0]
            for row in db.query(IncidentAlert.alert_id)
            .filter_by(incident_id=inc.incident_id)
            .all()
        ]
        results.append({
            "incident_id": inc.incident_id,
            "tenant_id": inc.tenant_id,
            "title": inc.title,
            "severity": inc.severity,
            "summary": inc.summary,
            "status": inc.status,
            "created_at": inc.created_at,
            "updated_at": inc.updated_at,
            "alert_count": len(linked_alert_ids),
            "linked_alert_ids": linked_alert_ids,
        })
    return results


@aiops_router.get("/insights")
def get_aiops_insights(
    tenant_id: str = DEFAULT_TENANT_ID,
    db: Session = Depends(get_db),
):
    """
    Returns unified evidence for the AIOps Insights page:
    - Rule-based detection evidence
    - Statistical anomaly detection evidence (with z-scores and baseline details)
    - LLM explanations and recommendations
    """
    rule_alerts = (
        db.query(Alert)
        .filter(Alert.tenant_id == tenant_id, Alert.detection_method == "rule")
        .order_by(Alert.created_at.desc())
        .limit(20)
        .all()
    )

    stat_alerts = (
        db.query(Alert)
        .filter(Alert.tenant_id == tenant_id, Alert.detection_method == "statistical")
        .order_by(Alert.created_at.desc())
        .limit(20)
        .all()
    )

    recommendations = (
        db.query(Recommendation)
        .order_by(Recommendation.created_at.desc())
        .limit(20)
        .all()
    )

    return {
        "rule_based_evidence": [
            {
                "alert_id": a.alert_id,
                "server_id": a.server_id,
                "severity": a.severity,
                "description": a.description,
                "created_at": a.created_at,
            }
            for a in rule_alerts
        ],
        "statistical_evidence": [
            {
                "alert_id": a.alert_id,
                "server_id": a.server_id,
                "severity": a.severity,
                "description": a.description,
                "created_at": a.created_at,
            }
            for a in stat_alerts
        ],
        "recommendations": [
            {
                "recommendation_id": r.recommendation_id,
                "incident_id": r.incident_id,
                "explanation": r.explanation,
                "recommended_action": r.recommended_action,
                "llm_generated": r.llm_generated,
                "approval_status": r.approval_status,
                "created_at": r.created_at,
            }
            for r in recommendations
        ],
    }
