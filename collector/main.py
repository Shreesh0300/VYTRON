"""
Local Collector Application Entry Point (Port 8002)
Runs Tier 1 background processes:
- Heartbeat loop
- Persistent queue drainer
"""
import sys
import os
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

from collector.database import init_db, SessionLocal
from collector.config import CONFIG
from collector.ingestion import router as ingestion_router
from collector.health_monitor import send_heartbeat, get_health
from collector.queue_manager import drain_queue
from collector.egress import get_egress_history
from collector.models import EgressQueue, TransferAudit, LocalEvent


async def heartbeat_background_task():
    """Periodically sends health heartbeat to Central SaaS."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await send_heartbeat(client)
            except Exception as e:
                pass
            await asyncio.sleep(CONFIG["heartbeat_interval"])


async def queue_drain_background_task():
    """Periodically processes the local SQLite egress queue."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await drain_queue(client)
            except Exception as e:
                pass
            await asyncio.sleep(2.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    hb_task = asyncio.create_task(heartbeat_background_task())
    drain_task = asyncio.create_task(queue_drain_background_task())
    yield
    hb_task.cancel()
    drain_task.cancel()


app = FastAPI(
    title="VYTRON Local Collector (Tier 1)",
    description="Privacy-first telemetry collector with local buffering and egress audit.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion_router)


@app.get("/")
def read_root():
    return {
        "service": "VYTRON Local Collector",
        "tier": "Tier 1 (Customer Environment)",
        "collector_id": CONFIG["collector_id"],
        "tenant_id": CONFIG["tenant_id"],
        "status": "operational",
    }


@app.get("/health")
def read_health():
    return get_health()


@app.get("/egress")
def read_egress_history(limit: int = 50):
    db = SessionLocal()
    try:
        return get_egress_history(db, limit)
    finally:
        db.close()


@app.get("/queue/status")
def read_queue_status():
    db = SessionLocal()
    try:
        pending = db.query(EgressQueue).filter_by(delivery_status="pending").count()
        retryable = db.query(EgressQueue).filter_by(delivery_status="retryable").count()
        delivered = db.query(EgressQueue).filter_by(delivery_status="delivered").count()
        failed = db.query(EgressQueue).filter_by(delivery_status="failed").count()
        total_events = db.query(LocalEvent).count()
        return {
            "pending": pending,
            "retryable": retryable,
            "delivered": delivered,
            "failed": failed,
            "total_local_events": total_events,
        }
    finally:
        db.close()
