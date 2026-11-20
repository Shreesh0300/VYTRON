"""
VYTRON — Infrastructure Simulator (FastAPI)
Runs on port 8001.  Background loops push telemetry to the collector
(port 8002) and periodically inject fault scenarios.

Start with:
    uvicorn simulator.main:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import sys
import os

# ── Path fix so ``shared`` and ``simulator`` packages resolve ────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI
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
from simulator.server_profiles import get_all_servers, get_server, list_server_ids
from simulator.telemetry_generator import generate_all_telemetry
from simulator.scenarios import (
    inject_random_scenario,
    inject_scenario,
    list_scenarios,
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
    servers and POST each event as JSON to the collector's /telemetry
    endpoint.
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
                        # Ensure timestamp is ISO string
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
                            logger.warning(
                                "Collector returned %d for %s/%s",
                                response.status_code,
                                event.source_id,
                                event.metric,
                            )

                    except httpx.ConnectError:
                        _stats["events_failed"] += 1
                        # Log once per batch, not per event
                        logger.debug(
                            "Collector unreachable — dropping event %s/%s",
                            event.source_id,
                            event.metric,
                        )
                    except httpx.HTTPError as exc:
                        _stats["events_failed"] += 1
                        logger.warning("HTTP error sending event: %s", exc)

                sent = _stats["events_sent"]
                failed = _stats["events_failed"]
                logger.info(
                    "Telemetry cycle complete — %d events generated "
                    "(total sent=%d, failed=%d)",
                    len(events),
                    sent,
                    failed,
                )

            except Exception as exc:
                logger.exception("Unexpected error in telemetry_loop: %s", exc)

            await asyncio.sleep(TELEMETRY_PUSH_INTERVAL)


async def scenario_loop() -> None:
    """
    Every SCENARIO_INJECT_INTERVAL seconds, inject a random scenario
    to keep the telemetry interesting and exercise downstream detection.
    """
    logger.info(
        "Scenario loop started — injecting every %.0fs", SCENARIO_INJECT_INTERVAL
    )

    # Wait one interval before the first injection so baseline data
    # has a chance to establish itself.
    await asyncio.sleep(SCENARIO_INJECT_INTERVAL)

    while True:
        try:
            result = inject_random_scenario()
            _stats["scenarios_injected"] += 1
            logger.info("Scenario injected: %s", result)
        except Exception as exc:
            logger.exception("Error in scenario_loop: %s", exc)

        await asyncio.sleep(SCENARIO_INJECT_INTERVAL)


# ── Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):  # type: ignore[type-arg]
    """Start background loops on startup; cancel them on shutdown."""
    # Ensure server profiles are initialised
    servers = get_all_servers()
    logger.info(
        "Simulator online — %d servers: %s",
        len(servers),
        ", ".join(sorted(servers.keys())),
    )

    t1 = asyncio.create_task(telemetry_loop(), name="telemetry_loop")
    t2 = asyncio.create_task(scenario_loop(), name="scenario_loop")
    _background_tasks.extend([t1, t2])

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
    description=(
        "Generates realistic telemetry for 10 simulated servers and pushes "
        "it to the collector service.  Supports manual and automatic fault "
        "scenario injection."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ── Request Models ───────────────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    scenario: str
    server_id: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
async def health_check() -> dict[str, Any]:
    """Health / readiness probe."""
    return {
        "service": "vytron-simulator",
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "server_count": len(get_all_servers()),
        "stats": dict(_stats),
    }


@app.get("/servers", tags=["servers"])
async def get_servers() -> dict[str, Any]:
    """Return current state snapshots for all simulated servers."""
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
        return {
            "error": f"Server '{server_id}' not found",
            "available": list_server_ids(),
        }
    return srv.snapshot()


@app.post("/scenarios/inject", tags=["scenarios"])
async def inject_scenario_endpoint(req: ScenarioRequest) -> dict[str, Any]:
    """Manually trigger a named scenario, optionally targeting a server."""
    result = inject_scenario(
        scenario_name=req.scenario,
        server_id=req.server_id,
    )
    _stats["scenarios_injected"] += 1
    return result


@app.get("/scenarios", tags=["scenarios"])
async def get_available_scenarios() -> dict[str, Any]:
    """List all registered scenario names."""
    return {
        "scenarios": list_scenarios(),
        "count": len(list_scenarios()),
    }


@app.get("/stats", tags=["diagnostics"])
async def get_stats() -> dict[str, Any]:
    """Return internal telemetry statistics."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": dict(_stats),
    }


# ── Direct Execution ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "simulator.main:app",
        host=SIMULATOR_HOST,
        port=SIMULATOR_PORT_NUM,
        log_level=LOG_LEVEL.lower(),
    )
