"""
VYTRON — Infrastructure Monitoring & Incident Prioritization Platform
FastAPI server serving REST APIs, real-time WebSocket telemetry, and static frontend.
Powered by the dynamic Randomized Incident Generation Engine.
"""

import os
import json
import asyncio
from typing import Set, Optional, Any
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends, Query, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from server.simulator import InfrastructureSimulator
from server.rag.pipeline import troubleshoot_incident, get_vector_store
from server.chatbot import process_chat_message, get_contextual_suggestions, chat_sessions
from server.auth import (
    auth_router,
    get_current_user_optional,
    get_current_user,
    require_admin,
    COOKIE_NAME,
    get_user_from_session,
)

# Global simulator instance
simulator = InfrastructureSimulator()

# Active WebSocket connections
active_connections: Set[WebSocket] = set()

async def broadcast_state():
    """Broadcasts current snapshot to all active WebSocket clients."""
    if not active_connections:
        return
    snapshot = simulator.get_snapshot()
    msg = json.dumps(snapshot)
    dead_conns = []
    for conn in list(active_connections):
        try:
            await conn.send_text(msg)
        except Exception:
            dead_conns.append(conn)

    for dead in dead_conns:
        if dead in active_connections:
            active_connections.remove(dead)

async def simulation_loop():
    """Background task ticking simulation every 1.5 seconds."""
    while True:
        try:
            if simulator.is_running:
                simulator.tick()
                await broadcast_state()
        except Exception as e:
            print(f"[Simulator Tick Error]: {e}")
        await asyncio.sleep(1.5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch background simulation loop
    task = asyncio.create_task(simulation_loop())
    yield
    # Shutdown: cancel task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="VYTRON AIOps Platform",
    description="Real-time 5-Server Infrastructure Monitoring & Incident Prioritization with Dynamic Randomized Incident Generation",
    version="2.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

# ── REST Models ─────────────────────────────────────────────────────────

class StartSimulationRequest(BaseModel):
    scenario: Optional[str] = "auto"
    server_count: Optional[int] = None
    mode: Optional[str] = "random"

class TroubleshootRequest(BaseModel):
    incident_id: Optional[str] = None
    incident: Optional[dict] = None

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    incident_context: Optional[dict] = None

class ClearChatRequest(BaseModel):
    session_id: str

# ── API Endpoints ───────────────────────────────────────────────────────

@app.get("/api/state")
def get_state():
    """Returns full in-memory system snapshot."""
    return simulator.get_snapshot()

@app.get("/api/scenarios")
def get_scenarios():
    """Returns dynamic simulation modes."""
    return {
        "modes": [
            {"id": "auto", "title": "Random Simulation (1-5 Servers)", "description": "Dynamically selects 1-5 unique servers and random issues"},
            {"id": "1", "title": "Targeted Incident (1 Server)", "description": "Concentrates issue on a single random server"},
            {"id": "2", "title": "Dual-Server Incident (2 Servers)", "description": "Selects two random servers with independent issues"},
            {"id": "3", "title": "Multi-Server Incident (3 Servers)", "description": "Selects three random servers simultaneously"},
            {"id": "5", "title": "Full Cluster Outage (All 5 Servers)", "description": "Triggers cascading issues across all five servers"},
        ],
        "active_simulation": simulator.active_plan,
    }

@app.post("/api/simulation/start")
async def start_simulation(req: StartSimulationRequest = StartSimulationRequest()):
    """Starts a new randomized simulation run."""
    count = req.server_count
    if count is None and req.scenario and req.scenario in ("1", "2", "3", "4", "5"):
        count = int(req.scenario)

    plan = simulator.start_simulation(server_count=count)
    simulator.tick()  # Immediate tick
    await broadcast_state()
    return {
        "status": "started",
        "plan": plan,
        "state": simulator.get_snapshot(),
    }

@app.post("/api/simulation/stop")
async def stop_simulation():
    """Stops the active simulation and freezes all processes."""
    simulator.stop_simulation()
    await broadcast_state()
    return {"status": "stopped", "state": simulator.get_snapshot()}

@app.post("/api/simulation/reset")
async def reset_simulation():
    """Resets all servers back to baseline, clears active incidents, and resets every process to the beginning."""
    simulator.reset()
    await broadcast_state()
    return {"status": "reset", "state": simulator.get_snapshot()}

@app.get("/api/egress/proof")
async def get_egress_proof(
    request: Request,
    tenant_id: Optional[str] = Query(None),
    include_raw: bool = Query(False),
    user: Optional[dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Returns the Egress Proof and transmission audit history with strict role-based access control.
    - Tenant isolation: returns 403 if requested tenant_id does not match the authorized tenant.
    - IT Team users: strictly prevented from retrieving Tier 1 raw payloads (returns 403 if include_raw is requested).
    - Admin users: access to raw customer data requires customer-local authorization.
    - By default: returns sanitized Tier 2 metadata and cryptographic audit proofs.
    """
    # 1. Enforce Tenant Isolation
    target_tenant = simulator.egress_engine.tenant_id  # "TENANT-01"
    if tenant_id and tenant_id.strip() != target_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Tenant isolation policy violation. Unauthorized tenant '{tenant_id}'."
        )

    # 2. Check Role & Tier 1 Raw Access Request
    if include_raw:
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to inspect Egress data."
            )
        user_role = user.get("authorized_role", "it_team")
        if user_role == "it_team":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: IT Team role is strictly prohibited from accessing customer-local Tier 1 raw telemetry and secrets."
            )
        # Admin: Access to Tier 1 raw customer data must remain subject to customer-local authorization
        local_auth_header = request.headers.get("X-Customer-Local-Auth", "").strip()
        local_auth_token = request.query_params.get("local_auth_token", "").strip()
        valid_local_keys = ["granted", "customer-local-authorized", os.getenv("COLLECTOR_API_KEY", "vytron-collector-key-2026")]
        is_local_authorized = (local_auth_header in valid_local_keys or local_auth_token in valid_local_keys)
        if not is_local_authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Central SaaS Administrator access to customer-local raw payloads requires explicit customer-local authorization."
            )

    return {
        "latest": simulator.egress_engine.get_latest_proof(include_raw=include_raw),
        "history": simulator.egress_engine.get_history(10, include_raw=include_raw),
        "stats": simulator.egress_engine.get_stats(),
        "role_access": {
            "authorized_role": user.get("authorized_role") if user else "unauthenticated",
            "tier1_raw_accessible": bool(include_raw),
            "tier2_sanitized_accessible": True,
            "tenant_id": target_tenant
        }
    }


@app.get("/api/egress/tier1-raw")
async def get_tier1_raw_telemetry(
    request: Request,
    tenant_id: Optional[str] = Query(None),
    user: dict[str, Any] = Depends(get_current_user)
):
    """
    Dedicated protected endpoint for customer-local Tier 1 raw telemetry inspection.
    - IT Team users: STRICTLY 403 Forbidden. Never allowed to view raw customer secrets.
    - Admin users: Subject to explicit customer-local on-premise authorization gate.
    - Tenant isolation: strictly enforced.
    """
    # 1. Tenant Isolation
    target_tenant = simulator.egress_engine.tenant_id
    if tenant_id and tenant_id.strip() != target_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Tenant isolation policy violation. Unauthorized tenant '{tenant_id}'."
        )

    # 2. Role Authorization
    user_role = user.get("authorized_role", "it_team")
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: IT Team role is strictly prohibited from accessing customer-local Tier 1 raw telemetry and secrets."
        )

    # 3. Customer-Local Authorization Gate for Admin
    local_auth_header = request.headers.get("X-Customer-Local-Auth", "").strip()
    local_auth_token = request.query_params.get("local_auth_token", "").strip()
    valid_local_keys = ["granted", "customer-local-authorized", os.getenv("COLLECTOR_API_KEY", "vytron-collector-key-2026")]
    is_local_authorized = (local_auth_header in valid_local_keys or local_auth_token in valid_local_keys)
    if not is_local_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Central SaaS Administrator requires explicit customer-local authorization to inspect raw on-premise logs and credentials."
        )

    raw_preview = simulator.egress_engine.get_tier1_raw_preview()
    return {
        "status": "authorized",
        "authorization_mode": "CUSTOMER_LOCAL_ON_PREM_AUTHORIZED",
        "audited_by": user.get("email"),
        "raw_tier1_record": raw_preview,
        "tenant_id": target_tenant
    }


@app.get("/api/egress/policy")
def get_egress_policy(tenant_id: Optional[str] = Query(None)):
    """Returns Tier 1 allow-list policy and field-level classification rules with tenant isolation."""
    target_tenant = simulator.egress_engine.tenant_id
    if tenant_id and tenant_id.strip() != target_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Tenant isolation policy violation. Unauthorized tenant '{tenant_id}'."
        )

    from server.privacy import ALLOWED_EGRESS_FIELDS, BLOCKED_RAW_KEYS, SENSITIVE_PATTERNS
    return {
        "tier1_trust_boundary": "Customer Local Environment (Local-First Security)",
        "tier2_saas": "Central SaaS Ingestion (Metadata Only)",
        "allowed_fields": ALLOWED_EGRESS_FIELDS,
        "blocked_raw_keys": list(BLOCKED_RAW_KEYS),
        "sensitive_patterns_count": len(SENSITIVE_PATTERNS),
        "tenant_id": target_tenant,
        "collector_id": simulator.egress_engine.collector_id,
        "classification": {
            "restricted_fields": [
                "passwords", "secrets", "jwt_tokens", "api_keys",
                "snmp_community_strings", "raw_sql", "internal_ips", "internal_gateway"
            ],
            "permitted_metadata_fields": ALLOWED_EGRESS_FIELDS
        }
    }

@app.post("/api/collector/outage/toggle")
def toggle_outage():
    """Toggles simulated SaaS link outage to demonstrate local buffering and zero-loss replay."""
    new_state = not simulator.egress_engine._outage_simulated
    res = simulator.egress_engine.set_outage(new_state)
    return res

@app.get("/api/servers")
def get_servers():
    """Returns all 5 servers current telemetry summary."""
    snapshot = simulator.get_snapshot()
    return {"servers": snapshot["servers"]}

@app.get("/api/servers/{server_id}")
def get_server_detail(server_id: str):
    """Returns specific server telemetry with complete 60-point history."""
    snapshot = simulator.get_snapshot()
    server = snapshot["servers"].get(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server

@app.get("/api/incidents")
def get_incidents():
    """Returns active priority queue and recent incident notifications."""
    snapshot = simulator.get_snapshot()
    return {
        "priority_queue": snapshot["priority_queue"],
        "notifications": snapshot["notifications"],
        "overview": snapshot["overview"],
    }

@app.post("/api/aiops/troubleshoot")
async def api_troubleshoot(req: TroubleshootRequest):
    """
    RAG-powered AI Troubleshooting:
    Retrieves relevant technical documentation chunks from ChromaDB and synthesizes
    8-section root-cause investigation guidance using the LLM / grounded expert engine.
    """
    target_incident = req.incident
    if not target_incident and req.incident_id:
        snapshot = simulator.get_snapshot()
        candidates = snapshot.get("priority_queue", []) + snapshot.get("notifications", [])
        for c in candidates:
            if c.get("incident_id") == req.incident_id:
                target_incident = c
                break

    if not target_incident:
        raise HTTPException(status_code=404, detail="Incident not found or no incident data provided")

    result = await troubleshoot_incident(target_incident)
    return result

@app.get("/api/knowledge/sources")
def get_knowledge_sources():
    """Returns catalog of loaded technical troubleshooting documentation."""
    store = get_vector_store()
    return {
        "sources": store.get_all_sources(),
        "total_chunks": store.collection.count(),
        "collection": "vytron_troubleshooting_kb"
    }

# ── AI IT Manager Support Chatbot Endpoints ──────────────────────────────

@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    """
    RAG-grounded AI IT Manager Support Chatbot:
    Validates IT operations scope, retrieves relevant vector chunks,
    integrates live simulator telemetry and generates structured troubleshooting guidance.
    """
    res = await process_chat_message(
        user_message=req.message,
        session_id=req.session_id,
        incident_context=req.incident_context,
        simulator_instance=simulator
    )
    return res

@app.get("/api/chat/health")
def api_chat_health():
    """Reports status of chatbot service, ChromaDB vector store, and embedding engine."""
    store = get_vector_store()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip("\"'")
    masked_key = f"{gemini_key[:3]}***{gemini_key[-4:]}" if len(gemini_key) > 8 else ("Configured" if gemini_key else "Not set")
    provider = os.getenv("LLM_PROVIDER", "gemini" if gemini_key else "fallback")
    return {
        "status": "healthy",
        "service": "VYTRON AI IT Support Assistant",
        "llm_provider": provider,
        "gemini_configured": bool(gemini_key),
        "gemini_key_preview": masked_key,
        "active_model": os.getenv("LLM_MODEL", "gemini-flash-lite-latest"),
        "vector_store": "connected",
        "collection": "vytron_troubleshooting_kb",
        "total_knowledge_chunks": store.collection.count() if store and store.collection else 0,
        "scope": "IT_INFRASTRUCTURE_OPERATIONS_ONLY",
        "mode": "RAG_Grounded_Hybrid"
    }

@app.get("/api/chat/suggestions")
def api_chat_suggestions(
    incident_id: Optional[str] = None,
    server_id: Optional[str] = None,
    metric: Optional[str] = None
):
    """Returns dynamic, contextual suggested troubleshooting questions based on incident context."""
    inc = None
    if incident_id:
        snapshot = simulator.get_snapshot()
        candidates = snapshot.get("priority_queue", []) + snapshot.get("notifications", [])
        for c in candidates:
            if c.get("incident_id") == incident_id:
                inc = c
                break
    if not inc and server_id:
        inc = {"server_id": server_id, "metric_key": metric or ""}

    suggestions = get_contextual_suggestions(inc)
    return {"suggestions": suggestions}

@app.post("/api/chat/clear")
def api_chat_clear(req: ClearChatRequest):
    """Clears conversation history for the specified session ID."""
    success = chat_sessions.clear(req.session_id)
    return {"session_id": req.session_id, "cleared": success}

# ── WebSocket Telemetry ─────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Enforce authentication barrier: Reject unauthenticated websocket telemetry streaming
    session_id = websocket.cookies.get(COOKIE_NAME)
    user = get_user_from_session(session_id) if session_id else None
    if not user or not user.get("authenticated"):
        # 1008 Policy Violation / Unauthorized
        await websocket.close(code=1008)
        return

    await websocket.accept()
    active_connections.add(websocket)
    try:
        # Immediately deliver current state on connection
        await websocket.send_text(json.dumps(simulator.get_snapshot()))
        while True:
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                action = cmd.get("action")
                if action == "start":
                    cnt = cmd.get("server_count") or cmd.get("count")
                    simulator.start_simulation(server_count=cnt)
                    simulator.tick()
                elif action == "stop":
                    simulator.stop_simulation()
                elif action == "reset":
                    simulator.reset()
                await broadcast_state()
            except Exception:
                pass
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)

# ── Mount Frontend Static Files & Hero Landing Routes ─────────────────────

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

@app.get("/hero")
@app.get("/hero.html")
@app.get("/landing")
@app.get("/landing.html")
def get_hero_landing():
    """Serves the VYTRON AIOps Hero & Platform Overview page."""
    return FileResponse(os.path.join(frontend_dir, "hero.html"))

@app.get("/")
@app.get("/index.html")
@app.get("/dashboard")
async def get_dashboard_root(request: Request):
    """
    Mandatory authentication barrier for the monitoring dashboard:
    Unauthenticated visitors are redirected to the home landing page (hero.html) to log in.
    Authenticated users (IT Team or Admin) are served index.html.
    """
    user = await get_current_user_optional(request)
    if not user or not user.get("user_id"):
        return RedirectResponse(url="/hero.html?auth_required=true", status_code=302)
    return FileResponse(os.path.join(frontend_dir, "index.html"))

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
