"""
VYTRON — Infrastructure Monitoring & Incident Prioritization Platform
FastAPI server serving REST APIs, real-time WebSocket telemetry, and static frontend.
Powered by the dynamic Randomized Incident Generation Engine.
"""

import os
import json
import asyncio
from typing import Set, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from server.simulator import InfrastructureSimulator
from server.rag.pipeline import troubleshoot_incident, get_vector_store
from server.chatbot import process_chat_message, get_contextual_suggestions, chat_sessions

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
def start_simulation(req: StartSimulationRequest = StartSimulationRequest()):
    """Starts a new randomized simulation run."""
    count = req.server_count
    if count is None and req.scenario and req.scenario in ("1", "2", "3", "4", "5"):
        count = int(req.scenario)

    plan = simulator.start_simulation(server_count=count)
    simulator.tick()  # Immediate tick
    return {
        "status": "started",
        "plan": plan,
        "state": simulator.get_snapshot(),
    }

@app.post("/api/simulation/stop")
def stop_simulation():
    """Stops the active simulation."""
    simulator.stop_simulation()
    return {"status": "stopped", "state": simulator.get_snapshot()}

@app.post("/api/simulation/reset")
def reset_simulation():
    """Resets all servers back to baseline and resolves active incidents."""
    simulator.reset()
    return {"status": "reset", "state": simulator.get_snapshot()}

@app.get("/api/egress/proof")
def get_egress_proof():
    """Returns the latest Egress Proof and recent transmission audit history."""
    return {
        "latest": simulator.egress_engine.get_latest_proof(),
        "history": simulator.egress_engine.get_history(10),
        "stats": simulator.egress_engine.get_stats(),
    }

@app.get("/api/egress/policy")
def get_egress_policy():
    """Returns Tier 1 allow-list policy and redaction rules."""
    from server.privacy import ALLOWED_EGRESS_FIELDS, BLOCKED_RAW_KEYS, SENSITIVE_PATTERNS
    return {
        "tier1_trust_boundary": "Customer Local Environment (Local-First Security)",
        "tier2_saas": "Central SaaS Ingestion (Metadata Only)",
        "allowed_fields": ALLOWED_EGRESS_FIELDS,
        "blocked_raw_keys": list(BLOCKED_RAW_KEYS),
        "sensitive_patterns_count": len(SENSITIVE_PATTERNS),
        "tenant_id": simulator.egress_engine.tenant_id,
        "collector_id": simulator.egress_engine.collector_id,
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
    return {
        "status": "healthy",
        "service": "VYTRON AI IT Support Assistant",
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
                elif action == "stop":
                    simulator.stop_simulation()
                elif action == "reset":
                    simulator.reset()
                simulator.tick()
                await broadcast_state()
            except Exception:
                pass
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)

# ── Mount Frontend Static Files ─────────────────────────────────────────

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
