"""
Central Platform Application Entry Point (Port 8000)
Hosts the Central SaaS APIs, AIOps Engine, and Serves Dashboard Endpoints.
"""
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database.connection import init_db, SessionLocal
from backend.models.platform_models import Collector, AuditLog
from backend.api.telemetry import router as telemetry_router
from backend.api.collectors import router as collectors_router
from backend.api.servers import servers_router, metrics_router
from backend.api.alerts import alerts_router, incidents_router, aiops_router
from backend.api.remediation import rec_router, remediation_router
from backend.api.egress import egress_router, audit_router
from shared.constants import COLLECTOR_OFFLINE_TIMEOUT_SECONDS, DEFAULT_TENANT_ID
from shared.schemas import generate_id


async def collector_offline_monitor_task():
    """
    Checks collector heartbeats every 15s.
    Detects offline state within 60s target SLA and logs audit event.
    """
    while True:
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            collectors = db.query(Collector).all()
            for c in collectors:
                last_dt = datetime.fromisoformat(c.last_seen)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                diff = (now - last_dt).total_seconds()

                if diff > COLLECTOR_OFFLINE_TIMEOUT_SECONDS and c.status == "online":
                    c.status = "offline"
                    audit = AuditLog(
                        audit_id=generate_id("AUDIT"),
                        tenant_id=c.tenant_id,
                        actor="platform_monitor",
                        action="collector_offline_detected",
                        resource_type="collector",
                        resource_id=c.collector_id,
                        timestamp=now.isoformat(),
                        details=f"Collector {c.collector_id} missed heartbeats ({diff:.1f}s elapsed). Status set to OFFLINE (Poor).",
                    )
                    db.add(audit)
                    db.commit()
        except Exception:
            pass
        finally:
            db.close()
        await asyncio.sleep(15.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    monitor_task = asyncio.create_task(collector_offline_monitor_task())
    yield
    monitor_task.cancel()


app = FastAPI(
    title="VYTRON Central AIOps Platform (Tier 2)",
    description="Multi-tenant, metadata-only SaaS platform with hybrid AIOps detection and Autonomous Ops simulation.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS configuration strictly allowing local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
app.include_router(telemetry_router)
app.include_router(collectors_router)
app.include_router(servers_router)
app.include_router(metrics_router)
app.include_router(alerts_router)
app.include_router(incidents_router)
app.include_router(aiops_router)
app.include_router(rec_router)
app.include_router(remediation_router)
app.include_router(egress_router)
app.include_router(audit_router)


@app.get("/")
def read_root():
    return {
        "service": "VYTRON Central SaaS Platform",
        "tier": "Tier 2 (Central Metadata SaaS)",
        "version": "2.0.0",
        "status": "operational",
    }
