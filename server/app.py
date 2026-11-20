"""
VYTRON — Infrastructure Monitoring & Incident Prioritization Platform
FastAPI server serving REST APIs, real-time WebSocket telemetry, and static frontend.
Single unified process on port 8000.
"""

import os
import json
import asyncio
from typing import Set
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
    description="Real-time 5-Server Infrastructure Monitoring & Incident Prioritization",
    version="2.0.0",
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

class StartScenarioRequest(BaseModel):
    scenario: str

# ── API Endpoints ───────────────────────────────────────────────────────

@app.get("/api/state")
def get_state():
    """Returns full in-memory system snapshot."""
    return simulator.get_snapshot()

@app.get("/api/scenarios")
def get_scenarios():
    """Returns available simulation scenarios."""
    snapshot = simulator.get_snapshot()
    return {"scenarios": snapshot["scenarios"], "active_scenario": snapshot["active_scenario"]}

@app.post("/api/simulation/start")
def start_simulation(req: StartScenarioRequest):
    """Starts a specific scenario."""
    success = simulator.start_scenario(req.scenario)
    if not success:
        raise HTTPException(status_code=400, detail=f"Invalid scenario ID '{req.scenario}'")
    simulator.tick()  # Immediate tick
    return {"status": "started", "scenario": req.scenario, "state": simulator.get_snapshot()}

@app.post("/api/simulation/stop")
def stop_simulation():
    """Stops the active scenario."""
    simulator.stop_scenario()
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

# ── WebSocket Telemetry ─────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        # Immediately deliver current state on connection
        await websocket.send_text(json.dumps(simulator.get_snapshot()))
        while True:
            # Listen for optional incoming messages (e.g. controls)
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                action = cmd.get("action")
                if action == "start":
                    simulator.start_scenario(cmd.get("scenario", "scenario_01"))
                elif action == "stop":
                    simulator.stop_scenario()
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
