"""
VYTRON — Scenario Engine
Implements fault-injection functions that mutate server state to simulate
real-world infrastructure incidents.  Each scenario modifies the ``current``
dict (and optionally ``metadata``) of one or more ServerState objects so
subsequent telemetry cycles reflect the degraded conditions.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Callable

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator.server_profiles import (
    ServerState,
    get_all_servers,
    get_server,
    list_server_ids,
)
from simulator.config import SCENARIO_WEIGHTS

logger = logging.getLogger("vytron.simulator.scenarios")


# ── Scenario Registry ───────────────────────────────────────────────────
# Populated by the @scenario decorator.

_SCENARIO_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {}


def scenario(name: str) -> Callable:
    """Decorator that registers a function as a named scenario."""

    def decorator(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        _SCENARIO_REGISTRY[name] = fn
        return fn

    return decorator


def get_scenario(name: str) -> Callable[..., dict[str, Any]] | None:
    """Return the scenario function for *name*, or None."""
    return _SCENARIO_REGISTRY.get(name)


def list_scenarios() -> list[str]:
    """Return all registered scenario names."""
    return list(_SCENARIO_REGISTRY.keys())


# ── Helper ──────────────────────────────────────────────────────────────

def _pick_server(server_id: str | None, *preferred_types: str) -> ServerState | None:
    """
    Resolve a target server.  If *server_id* is given, use it.  Otherwise
    pick a random server whose type is in *preferred_types* (or any server
    if no types specified).
    """
    if server_id:
        srv = get_server(server_id)
        if srv is None:
            logger.warning("Server %s not found", server_id)
        return srv

    servers = get_all_servers()
    if preferred_types:
        candidates = [s for s in servers.values() if s.server_type in preferred_types]
    else:
        candidates = list(servers.values())

    if not candidates:
        logger.warning("No candidate servers available")
        return None

    return random.choice(candidates)


# ── Scenario Implementations ────────────────────────────────────────────

@scenario("cpu_spike")
def cpu_spike(server_id: str | None = None) -> dict[str, Any]:
    """Spike CPU usage to 85–98 % on a target server."""
    srv = _pick_server(server_id, "application", "web", "database")
    if srv is None:
        return {"status": "skipped", "reason": "no server found"}

    new_cpu = round(random.uniform(85.0, 98.0), 2)
    srv.current["cpu_usage"] = new_cpu
    logger.info("cpu_spike → %s cpu_usage=%.1f%%", srv.server_id, new_cpu)
    return {
        "status": "injected",
        "scenario": "cpu_spike",
        "server_id": srv.server_id,
        "cpu_usage": new_cpu,
    }


@scenario("memory_exhaustion")
def memory_exhaustion(server_id: str | None = None) -> dict[str, Any]:
    """Push memory usage to 92–99 % on a target server."""
    srv = _pick_server(server_id, "application", "database")
    if srv is None:
        return {"status": "skipped", "reason": "no server found"}

    new_mem = round(random.uniform(92.0, 99.0), 2)
    srv.current["memory_usage"] = new_mem
    logger.info("memory_exhaustion → %s memory_usage=%.1f%%", srv.server_id, new_mem)
    return {
        "status": "injected",
        "scenario": "memory_exhaustion",
        "server_id": srv.server_id,
        "memory_usage": new_mem,
    }


@scenario("disk_pressure")
def disk_pressure(server_id: str | None = None) -> dict[str, Any]:
    """Increase disk usage to 88–95 % on a target server."""
    srv = _pick_server(server_id, "storage", "database", "backup")
    if srv is None:
        return {"status": "skipped", "reason": "no server found"}

    new_disk = round(random.uniform(88.0, 95.0), 2)
    srv.current["disk_usage"] = new_disk
    logger.info("disk_pressure → %s disk_usage=%.1f%%", srv.server_id, new_disk)
    return {
        "status": "injected",
        "scenario": "disk_pressure",
        "server_id": srv.server_id,
        "disk_usage": new_disk,
    }


@scenario("database_failure")
def database_failure(server_id: str | None = None) -> dict[str, Any]:
    """Take DB-01 (or specified DB) offline — service_availability → 0."""
    srv = _pick_server(server_id, "database")
    if srv is None:
        return {"status": "skipped", "reason": "no server found"}

    srv.current["service_availability"] = 0.0
    srv.current["cpu_usage"] = round(random.uniform(0.5, 5.0), 2)
    logger.info("database_failure → %s is DOWN", srv.server_id)
    return {
        "status": "injected",
        "scenario": "database_failure",
        "server_id": srv.server_id,
        "service_availability": 0.0,
    }


@scenario("service_outage")
def service_outage(server_id: str | None = None) -> dict[str, Any]:
    """
    Simulate a service outage on WEB-01 and APP-01 (or a specified server).
    Sets service_availability to 0 and drops CPU to near-idle.
    """
    if server_id:
        targets = [server_id]
    else:
        targets = ["WEB-01", "APP-01"]

    affected: list[str] = []
    for sid in targets:
        srv = get_server(sid)
        if srv is None:
            continue
        srv.current["service_availability"] = 0.0
        srv.current["cpu_usage"] = round(random.uniform(0.5, 3.0), 2)
        affected.append(sid)
        logger.info("service_outage → %s is DOWN", sid)

    return {
        "status": "injected" if affected else "skipped",
        "scenario": "service_outage",
        "affected_servers": affected,
    }


@scenario("network_latency_spike")
def network_latency_spike(server_id: str | None = None) -> dict[str, Any]:
    """Spike network latency to 200–500 ms on NETWORK-01 (or specified)."""
    srv = _pick_server(server_id, "network")
    if srv is None:
        srv = get_server("NETWORK-01")
    if srv is None:
        return {"status": "skipped", "reason": "no server found"}

    new_latency = round(random.uniform(200.0, 500.0), 2)
    srv.current["network_latency"] = new_latency
    logger.info(
        "network_latency_spike → %s latency=%.1fms", srv.server_id, new_latency
    )
    return {
        "status": "injected",
        "scenario": "network_latency_spike",
        "server_id": srv.server_id,
        "network_latency": new_latency,
    }


@scenario("packet_loss_spike")
def packet_loss_spike(server_id: str | None = None) -> dict[str, Any]:
    """Spike packet loss to 5–15 % on NETWORK-01 (or specified)."""
    srv = _pick_server(server_id, "network")
    if srv is None:
        srv = get_server("NETWORK-01")
    if srv is None:
        return {"status": "skipped", "reason": "no server found"}

    new_loss = round(random.uniform(5.0, 15.0), 2)
    srv.current["packet_loss"] = new_loss
    logger.info("packet_loss_spike → %s packet_loss=%.1f%%", srv.server_id, new_loss)
    return {
        "status": "injected",
        "scenario": "packet_loss_spike",
        "server_id": srv.server_id,
        "packet_loss": new_loss,
    }


@scenario("failed_logins")
def failed_logins_scenario(server_id: str | None = None) -> dict[str, Any]:
    """Inject a burst of failed logins (10–25) on AUTH-01 (or specified)."""
    srv = _pick_server(server_id, "authentication")
    if srv is None:
        srv = get_server("AUTH-01")
    if srv is None:
        return {"status": "skipped", "reason": "no server found"}

    new_count = round(random.uniform(10.0, 25.0), 2)
    srv.current["failed_logins"] = new_count
    logger.info("failed_logins → %s count=%.0f", srv.server_id, new_count)
    return {
        "status": "injected",
        "scenario": "failed_logins",
        "server_id": srv.server_id,
        "failed_logins": new_count,
    }


@scenario("recovery")
def recovery(server_id: str | None = None) -> dict[str, Any]:
    """
    Restore one or all servers to baseline.  If *server_id* is given, only
    that server recovers; otherwise every server resets.
    """
    if server_id:
        srv = get_server(server_id)
        if srv is None:
            return {"status": "skipped", "reason": "server not found"}
        srv.reset_to_baseline()
        logger.info("recovery → %s restored to baseline", srv.server_id)
        return {
            "status": "injected",
            "scenario": "recovery",
            "server_id": srv.server_id,
        }

    # Recover all
    for srv in get_all_servers().values():
        srv.reset_to_baseline()
    logger.info("recovery → all servers restored to baseline")
    return {
        "status": "injected",
        "scenario": "recovery",
        "affected_servers": list_server_ids(),
    }


@scenario("sensitive_data_injection")
def sensitive_data_injection(server_id: str | None = None) -> dict[str, Any]:
    """
    Inject sensitive-looking keys (password, api_key) into a server's
    metadata so the privacy filter in the collector can be tested.
    """
    srv = _pick_server(server_id)
    if srv is None:
        return {"status": "skipped", "reason": "no server found"}

    srv.metadata["password"] = "P@ssw0rd!SuperSecret123"
    srv.metadata["api_key"] = "sk-live-FAKE-KEY-1234567890abcdef"
    srv.metadata["authorization"] = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake"
    srv.metadata["private_key"] = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn..."
    srv.metadata["debug_note"] = "This is a benign metadata field"

    logger.info(
        "sensitive_data_injection → %s metadata poisoned with %d sensitive keys",
        srv.server_id,
        4,
    )
    return {
        "status": "injected",
        "scenario": "sensitive_data_injection",
        "server_id": srv.server_id,
        "injected_keys": ["password", "api_key", "authorization", "private_key"],
    }


# ── Random Injection ────────────────────────────────────────────────────

def inject_random_scenario() -> dict[str, Any]:
    """
    Pick a random scenario weighted by SCENARIO_WEIGHTS and execute it
    against a randomly chosen appropriate server.
    """
    names = list(SCENARIO_WEIGHTS.keys())
    weights = [SCENARIO_WEIGHTS[n] for n in names]
    chosen_name = random.choices(names, weights=weights, k=1)[0]

    fn = get_scenario(chosen_name)
    if fn is None:
        logger.error("Scenario '%s' is weighted but not registered", chosen_name)
        return {"status": "error", "reason": f"unknown scenario: {chosen_name}"}

    logger.info("inject_random_scenario → selected '%s'", chosen_name)
    return fn()


# ── Manual / API Injection ──────────────────────────────────────────────

def inject_scenario(scenario_name: str, server_id: str | None = None) -> dict[str, Any]:
    """
    Execute a named scenario, optionally targeting a specific server.
    Returns a result dict with at least ``status`` and ``scenario`` keys.
    """
    fn = get_scenario(scenario_name)
    if fn is None:
        return {
            "status": "error",
            "reason": f"unknown scenario: {scenario_name}",
            "available": list_scenarios(),
        }
    return fn(server_id=server_id)
