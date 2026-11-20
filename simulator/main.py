"""
VYTRON — Infrastructure Simulator (FastAPI)
Runs on port 8001. Background loops push continuous live telemetry for all 10
servers to the local collector (port 8002). Exposes demo scenarios,
dynamic logs, and server-level interactive controls.

Start with:
    uvicorn simulator.main:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.schemas import RawTelemetryEvent
from simulator.config import (
    COLLECTOR_TELEMETRY_ENDPOINT,
    HTTP_TIMEOUT_SECONDS,
    LOG_FORMAT,
    LOG_LEVEL,
    SIMULATOR_HOST,
    SIMULATOR_PORT_NUM,
    TELEMETRY_PUSH_INTERVAL,
    SCENARIO_INJECT_INTERVAL,
)
from simulator.server_profiles import (
    get_all_servers,
    get_server,
    list_server_ids,
    reset_all_servers,
)
from simulator.telemetry_generator import generate_all_telemetry
from simulator.scenarios import (
    inject_random_scenario,
    inject_scenario,
    list_scenarios,
    get_active_scenario,
    control_server_metric,
    fail_single_server,
    recover_single_server,
)

# ── Logging ──────────────────────────────────────────────────────────────

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger("vytron.simulator")

# ── Background task handles ─────────────────────────────────────────────

_background_tasks: list[asyncio.Task[None]] = []

# ── Telemetry statistics ────────────────────────────────────────────────

_stats: dict[str, int] = {
    "events_generated": 0,
    "events_sent": 0,
    "events_failed": 0,
    "scenarios_injected": 0,
}


# ── Background Loops ────────────────────────────────────────────────────

async def telemetry_loop() -> None:
    """
    Every TELEMETRY_PUSH_INTERVAL seconds, generate telemetry for all 10
    servers and POST each event to the collector's /telemetry endpoint.
    """
    logger.info(
        "Telemetry loop started — pushing every %.1fs to %s",
        TELEMETRY_PUSH_INTERVAL,
        COLLECTOR_TELEMETRY_ENDPOINT,
    )

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        while True:
            try:
                events: list[RawTelemetryEvent] = generate_all_telemetry()
                _stats["events_generated"] += len(events)

                for event in events:
                    try:
                        payload = event.model_dump(mode="json")
                        if isinstance(payload.get("timestamp"), datetime):
                            payload["timestamp"] = payload["timestamp"].isoformat()

                        response = await client.post(
                            COLLECTOR_TELEMETRY_ENDPOINT,
                            json=payload,
                        )

                        if response.status_code in (200, 201, 202):
                            _stats["events_sent"] += 1
                        else:
                            _stats["events_failed"] += 1

                    except httpx.ConnectError:
                        _stats["events_failed"] += 1
                    except httpx.HTTPError:
                        _stats["events_failed"] += 1

            except Exception as exc:
                logger.exception("Unexpected error in telemetry_loop: %s", exc)

            await asyncio.sleep(TELEMETRY_PUSH_INTERVAL)


# ── Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):  # type: ignore[type-arg]
    """Start telemetry loop on startup; cancel on shutdown."""
    servers = get_all_servers()
    logger.info(
        "Simulator online — %d servers: %s",
        len(servers),
        ", ".join(sorted(servers.keys())),
    )

    t1 = asyncio.create_task(telemetry_loop(), name="telemetry_loop")
    _background_tasks.append(t1)

    yield

    logger.info("Shutting down background loops …")
    for task in _background_tasks:
        task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()
    logger.info("Simulator stopped.")


# ── FastAPI Application ─────────────────────────────────────────────────

app = FastAPI(
    title="VYTRON — Infrastructure Simulator",
    description="Generates continuous live telemetry for 10 servers and supports demo scenarios.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Models ───────────────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    scenario: str
    server_id: str | None = None


class ServerActionRequest(BaseModel):
    server_id: str
    action: str  # fail | recover | set_metric
    metric: str | None = None
    value: float | None = None


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
async def health_check() -> dict[str, Any]:
    return {
        "service": "vytron-simulator",
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "server_count": len(get_all_servers()),
        "active_scenario": get_active_scenario(),
        "stats": dict(_stats),
    }


@app.get("/servers", tags=["servers"])
async def get_servers() -> dict[str, Any]:
    """Return live snapshots and metrics for all 10 servers."""
    servers = get_all_servers()
    return {
        "server_count": len(servers),
        "servers": {sid: srv.snapshot() for sid, srv in sorted(servers.items())},
    }


@app.get("/servers/{server_id}", tags=["servers"])
async def get_single_server(server_id: str) -> dict[str, Any]:
    """Return the state snapshot for a single server."""
    srv = get_server(server_id.upper())
    if srv is None:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
    return srv.snapshot()


@app.get("/servers/{server_id}/logs", tags=["servers"])
async def get_server_logs(server_id: str) -> dict[str, Any]:
    """Return live dynamic log history for a server."""
    srv = get_server(server_id.upper())
    if srv is None:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found")
    return {
        "server_id": srv.server_id,
        "server_name": srv.name,
        "logs": list(srv.log_history),
    }


@app.post("/scenarios/demo-scenario", tags=["scenarios"])
async def trigger_demo_scenario(req: ScenarioRequest) -> dict[str, Any]:
    """Execute one of the 8 judge demo scenarios."""
    result = inject_scenario(req.scenario, server_id=req.server_id)
    _stats["scenarios_injected"] += 1
    return {
        "active_scenario": get_active_scenario(),
        "result": result,
    }


@app.post("/scenarios/server-action", tags=["scenarios"])
async def perform_server_action(req: ServerActionRequest) -> dict[str, Any]:
    """Perform a fine-grained action on a specific server."""
    sid = req.server_id.upper()
    if req.action == "fail":
        return fail_single_server(sid)
    elif req.action == "recover":
        return recover_single_server(sid)
    elif req.action == "set_metric":
        if not req.metric or req.value is None:
            raise HTTPException(status_code=400, detail="Missing metric or value for set_metric action")
        return control_server_metric(sid, req.metric, req.value)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action '{req.action}'")


@app.post("/scenarios/reset", tags=["scenarios"])
async def reset_all_servers_endpoint() -> dict[str, Any]:
    """Reset every server to baseline."""
    reset_all_servers()
    return {
        "status": "success",
        "message": "All servers reset to baseline operational state",
        "active_scenario": get_active_scenario(),
    }


@app.get("/scenarios/active", tags=["scenarios"])
async def get_active_scenario_endpoint() -> dict[str, Any]:
    """Return the name of the currently active scenario."""
    return {"active_scenario": get_active_scenario()}


@app.post("/scenarios/inject", tags=["scenarios"])
async def inject_scenario_endpoint(req: ScenarioRequest) -> dict[str, Any]:
    """Generic scenario injection endpoint."""
    result = inject_scenario(req.scenario, server_id=req.server_id)
    _stats["scenarios_injected"] += 1
    return result


@app.get("/scenarios", tags=["scenarios"])
async def get_available_scenarios() -> dict[str, Any]:
    return {
        "scenarios": list_scenarios(),
        "active_scenario": get_active_scenario(),
        "count": len(list_scenarios()),
    }


@app.get("/stats", tags=["diagnostics"])
async def get_stats() -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": dict(_stats),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "simulator.main:app",
        host=SIMULATOR_HOST,
        port=SIMULATOR_PORT_NUM,
        log_level=LOG_LEVEL.lower(),
    )
