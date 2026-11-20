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

# ── Egress Proof & Privacy Audit Endpoints ──────────────────────────────

@app.get("/api/egress/stats")
def read_egress_stats():
    """Returns actual aggregated egress statistics from collector.db."""
    from server.egress_service import get_egress_stats
    return get_egress_stats()

@app.get("/api/egress")
def read_egress_records(limit: int = 50, filter_type: Optional[str] = None, server: Optional[str] = None):
    """Returns actual payload audit records from collector.db."""
    from server.egress_service import get_egress_records
    return get_egress_records(limit=limit, filter_type=filter_type, server=server)

@app.get("/api/egress/{payload_id}")
def read_payload_detail(payload_id: str):
    """Returns exact Before vs After comparison and serialized outgoing JSON."""
    from server.egress_service import get_payload_detail
    detail = get_payload_detail(payload_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Payload {payload_id} not found in audit records")
    return detail

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
