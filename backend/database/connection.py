"""
Central Platform Database Connection (platform.db - Tier 2)
"""
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.constants import (
    DEFAULT_TENANT_ID,
    DEFAULT_COLLECTOR_ID,
    SERVER_PROFILES,
)

DB_PATH = Path(__file__).resolve().parent.parent / "platform.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from backend.models.platform_models import (
        Tenant,
        Collector,
        Server,
        AuditLog,
    )
    from datetime import datetime, timezone

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed Tenant
        tenant = db.query(Tenant).filter_by(tenant_id=DEFAULT_TENANT_ID).first()
        if not tenant:
            tenant = Tenant(
                tenant_id=DEFAULT_TENANT_ID,
                tenant_name="Acme Global Enterprise",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(tenant)

        # Seed Collector
        collector = db.query(Collector).filter_by(collector_id=DEFAULT_COLLECTOR_ID).first()
        if not collector:
            collector = Collector(
                collector_id=DEFAULT_COLLECTOR_ID,
                tenant_id=DEFAULT_TENANT_ID,
                status="online",
                last_seen=datetime.now(timezone.utc).isoformat(),
                software_version="1.0.0",
                cpu_usage=12.5,
                memory_usage=34.0,
                configuration_status="configured",
            )
            db.add(collector)

        # Seed 10 Server Profiles
        for s_id, s_info in SERVER_PROFILES.items():
            server = db.query(Server).filter_by(server_id=s_id).first()
            if not server:
                server = Server(
                    server_id=s_id,
                    tenant_id=DEFAULT_TENANT_ID,
                    collector_id=DEFAULT_COLLECTOR_ID,
                    server_name=s_info["name"],
                    server_type=s_info["type"],
                    status="excellent",
                )
                db.add(server)

        # Audit initial bootstrap (only if not already recorded)
        existing_audit = db.query(AuditLog).filter_by(audit_id="BOOTSTRAP-01").first()
        if not existing_audit:
            audit = AuditLog(
                audit_id="BOOTSTRAP-01",
                tenant_id=DEFAULT_TENANT_ID,
                actor="system",
                action="platform_init",
                resource_type="system",
                resource_id="platform.db",
                timestamp=datetime.now(timezone.utc).isoformat(),
                details="Initialized platform database tables and baseline seeds",
            )
            db.add(audit)
        db.commit()
    finally:
        db.close()
