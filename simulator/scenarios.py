"""
VYTRON — Scenario Engine
Implements fault-injection functions that mutate server state to simulate
real-world infrastructure incidents, including 8 predefined judge demo scenarios
and fine-grained server-level interactive controls.
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
    reset_all_servers,
    apply_cascading_dependencies,
)
from simulator.config import SCENARIO_WEIGHTS

logger = logging.getLogger("vytron.simulator.scenarios")

# Track current active scenario name for UI indicator
_active_scenario: str = "Normal Operations"


def get_active_scenario() -> str:
    return _active_scenario


def set_active_scenario(name: str) -> None:
    global _active_scenario
    _active_scenario = name


# ── Scenario Registry ───────────────────────────────────────────────────

_SCENARIO_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {}


def scenario(name: str) -> Callable:
    """Decorator that registers a function as a named scenario."""
    def decorator(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        _SCENARIO_REGISTRY[name] = fn
        return fn
    return decorator


def get_scenario(name: str) -> Callable[..., dict[str, Any]] | None:
    return _SCENARIO_REGISTRY.get(name)


def list_scenarios() -> list[str]:
    return list(_SCENARIO_REGISTRY.keys())


# ── Helper ──────────────────────────────────────────────────────────────

def _pick_server(server_id: str | None, *preferred_types: str) -> ServerState | None:
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


# ── 8 Predefined Judge Demo Scenarios ───────────────────────────────────

@scenario("demo_normal")
def demo_normal() -> dict[str, Any]:
    """Scenario 1: Normal Operations — restores all 10 servers to baseline."""
    reset_all_servers()
    set_active_scenario("Normal Operations")
    logger.info("Demo Scenario 1: Normal Operations restored across all 10 servers.")
    return {
        "status": "success",
        "scenario": "demo_normal",
        "title": "Normal Operations",
        "description": "All 10 servers operating with healthy baselines.",
    }


@scenario("demo_cpu_spike")
def demo_cpu_spike(server_id: str = "APP-01") -> dict[str, Any]:
    """Scenario 2: High CPU Spike on APP-01 (or selected)."""
    srv = get_server(server_id) or get_server("APP-01")
    if not srv:
        return {"status": "error", "message": "Server not found"}

    srv.current["cpu_usage"] = round(random.uniform(92.0, 97.5), 1)
    srv.current["response_time"] = round(random.uniform(420.0, 520.0), 1)
    srv.current["error_rate"] = round(random.uniform(4.5, 8.2), 2)
    srv.activity = f"Thread Pool Saturation: High CPU usage ({srv.current['cpu_usage']}%)"
    srv.add_log("CRITICAL", f"Thread starvation: CPU reached {srv.current['cpu_usage']}%. Latency rising.")

    set_active_scenario(f"High CPU Spike ({srv.server_id})")
    return {
        "status": "success",
        "scenario": "demo_cpu_spike",
        "server_id": srv.server_id,
        "cpu_usage": srv.current["cpu_usage"],
        "response_time": srv.current["response_time"],
    }


@scenario("demo_db_failure")
def demo_db_failure() -> dict[str, Any]:
    """
    Scenario 3: Database Failure with Service Cascade:
    DB-01 crashes -> cascades errors to APP-01 -> cascades timeouts to WEB-01.
    """
    db01 = get_server("DB-01")
    if not db01:
        return {"status": "error", "message": "DB-01 not found"}

    db01.is_failed = True
    db01.current["service_availability"] = 0.0
    db01.current["error_rate"] = 100.0
    db01.current["cpu_usage"] = 2.0
    db01.activity = "PostgreSQL daemon terminated abnormally (exit code 139)"
    db01.add_log("CRITICAL", "FATAL: Database engine crashed. Connection pool closed.")

    # Trigger cascade
    apply_cascading_dependencies(get_all_servers())
    set_active_scenario("Database Failure & Cascade (DB-01 ➔ APP-01 ➔ WEB-01)")

    return {
        "status": "success",
        "scenario": "demo_db_failure",
        "root_cause": "DB-01",
        "cascaded_services": ["APP-01", "WEB-01"],
        "description": "DB-01 offline, causing cascading failures in APP-01 and WEB-01.",
    }


@scenario("demo_auth_spike")
def demo_auth_spike() -> dict[str, Any]:
    """Scenario 4: Authentication Security Incident on AUTH-01."""
    auth01 = get_server("AUTH-01")
    if not auth01:
        return {"status": "error", "message": "AUTH-01 not found"}

    auth01.current["failed_logins"] = 28.0
    auth01.current["request_rate"] = 390.0
    auth01.current["response_time"] = 210.0
    auth01.current["cpu_usage"] = 78.5
    auth01.activity = "Security Alert: Brute-force credential stuffing attack detected"
    auth01.add_log("CRITICAL", "Ingress security alert: 28 failed logins/min. Rate-limit enforced.")

    apply_cascading_dependencies(get_all_servers())
    set_active_scenario("Authentication Spike & Attack (AUTH-01)")

    return {
        "status": "success",
        "scenario": "demo_auth_spike",
        "server_id": "AUTH-01",
        "failed_logins": auth01.current["failed_logins"],
        "description": "High failed login rate and request surge on AUTH-01.",
    }


@scenario("demo_network_degradation")
def demo_network_degradation() -> dict[str, Any]:
    """Scenario 5: Network Server Degradation on NETWORK-01."""
    net01 = get_server("NETWORK-01")
    if not net01:
        return {"status": "error", "message": "NETWORK-01 not found"}

    net01.current["packet_loss"] = 12.8
    net01.current["network_latency"] = 360.0
    net01.activity = "Core switch interface degradation: 12.8% packet loss"
    net01.add_log("CRITICAL", "Switch hardware fault on eth0: High packet loss and CRC checksum errors.")

    apply_cascading_dependencies(get_all_servers())
    set_active_scenario("Network Degradation (NETWORK-01)")

    return {
        "status": "success",
        "scenario": "demo_network_degradation",
        "server_id": "NETWORK-01",
        "packet_loss": net01.current["packet_loss"],
        "latency": net01.current["network_latency"],
        "description": "High packet loss and latency on NETWORK-01 propagating across cluster.",
    }


@scenario("demo_storage_pressure")
def demo_storage_pressure() -> dict[str, Any]:
    """Scenario 6: Storage Capacity Exhaustion on STORAGE-01."""
    storage = get_server("STORAGE-01")
    if not storage:
        return {"status": "error", "message": "STORAGE-01 not found"}

    storage.current["disk_usage"] = 96.4
    storage.current["response_time"] = 320.0
    storage.activity = "Storage volume full: /data partition at 96.4% capacity"
    storage.add_log("CRITICAL", "Filesystem capacity alert: Volume STORAGE-01 disk usage at 96.4%.")

    apply_cascading_dependencies(get_all_servers())
    set_active_scenario("Storage Pressure (STORAGE-01 ➔ BACKUP-01)")

    return {
        "status": "success",
        "scenario": "demo_storage_pressure",
        "server_id": "STORAGE-01",
        "disk_usage": storage.current["disk_usage"],
        "description": "Disk capacity exhaustion on STORAGE-01 causing BACKUP-01 to abort.",
    }


@scenario("demo_app_failure")
def demo_app_failure() -> dict[str, Any]:
    """Scenario 7: Application Server Outage on APP-01."""
    app01 = get_server("APP-01")
    if not app01:
        return {"status": "error", "message": "APP-01 not found"}

    app01.is_failed = True
    app01.current["service_availability"] = 0.0
    app01.current["error_rate"] = 100.0
    app01.activity = "Application crash: java.lang.OutOfMemoryError (Heap dump written)"
    app01.add_log("CRITICAL", "Fatal: Application runtime crashed. Service stopped responding.")

    apply_cascading_dependencies(get_all_servers())
    set_active_scenario("Application Outage (APP-01 ➔ WEB-01)")

    return {
        "status": "success",
        "scenario": "demo_app_failure",
        "server_id": "APP-01",
        "description": "APP-01 process crashed, causing WEB-01 to return HTTP 502 Bad Gateway.",
    }


@scenario("demo_full_recovery")
def demo_full_recovery() -> dict[str, Any]:
    """Scenario 8: Full Cluster Recovery."""
    reset_all_servers()
    set_active_scenario("Full Recovery Completed")
    logger.info("Demo Scenario 8: Full cluster recovery executed.")
    return {
        "status": "success",
        "scenario": "demo_full_recovery",
        "description": "All 10 servers reset and verified healthy.",
    }


# ── Fine-Grained Server-Level Controls ───────────────────────────────────

def control_server_metric(server_id: str, metric: str, value: float) -> dict[str, Any]:
    """Set a specific metric value on a target server."""
    srv = get_server(server_id)
    if not srv:
        return {"status": "error", "message": f"Server {server_id} not found"}

    srv.current[metric] = round(float(value), 2)
    srv.add_log("WARNING", f"Manual override: {metric} set to {srv.current[metric]}")
    apply_cascading_dependencies(get_all_servers())
    return {
        "status": "success",
        "server_id": server_id,
        "metric": metric,
        "value": srv.current[metric],
    }


def fail_single_server(server_id: str) -> dict[str, Any]:
    """Immediately simulate server crash / failure."""
    srv = get_server(server_id)
    if not srv:
        return {"status": "error", "message": f"Server {server_id} not found"}

    srv.is_failed = True
    srv.current["service_availability"] = 0.0
    srv.current["error_rate"] = 100.0
    srv.activity = f"Manual Fault Injection: Server {server_id} forced offline"
    srv.add_log("CRITICAL", f"Forced crash: Server {server_id} marked OFFLINE by administrator.")
    apply_cascading_dependencies(get_all_servers())
    return {
        "status": "success",
        "server_id": server_id,
        "action": "fail",
        "health": "OFFLINE",
    }


def recover_single_server(server_id: str) -> dict[str, Any]:
    """Immediately restore single server to healthy baseline."""
    srv = get_server(server_id)
    if not srv:
        return {"status": "error", "message": f"Server {server_id} not found"}

    srv.reset_to_baseline()
    apply_cascading_dependencies(get_all_servers())
    return {
        "status": "success",
        "server_id": server_id,
        "action": "recover",
        "health": "ONLINE",
    }


# ── Backward Compatible Scenarios ───────────────────────────────────────

@scenario("cpu_spike")
def cpu_spike(server_id: str | None = None) -> dict[str, Any]:
    srv = _pick_server(server_id, "application", "web", "database")
    if srv is None:
        return {"status": "skipped", "reason": "no server found"}
    return demo_cpu_spike(srv.server_id)


@scenario("memory_exhaustion")
def memory_exhaustion(server_id: str | None = None) -> dict[str, Any]:
    srv = _pick_server(server_id, "application", "database")
    if srv is None:
        return {"status": "skipped", "reason": "no server found"}
    srv.current["memory_usage"] = round(random.uniform(92.0, 98.5), 1)
    srv.activity = f"Memory Exhaustion: RAM at {srv.current['memory_usage']}%"
    srv.add_log("CRITICAL", f"High memory usage: {srv.current['memory_usage']}% RAM consumed.")
    return {"status": "injected", "scenario": "memory_exhaustion", "server_id": srv.server_id, "memory_usage": srv.current["memory_usage"]}


@scenario("disk_pressure")
def disk_pressure(server_id: str | None = None) -> dict[str, Any]:
    return demo_storage_pressure()


@scenario("database_failure")
def database_failure(server_id: str | None = None) -> dict[str, Any]:
    return demo_db_failure()


@scenario("service_outage")
def service_outage(server_id: str | None = None) -> dict[str, Any]:
    return demo_app_failure()


@scenario("network_latency_spike")
def network_latency_spike(server_id: str | None = None) -> dict[str, Any]:
    return demo_network_degradation()


@scenario("packet_loss_spike")
def packet_loss_spike(server_id: str | None = None) -> dict[str, Any]:
    return demo_network_degradation()


@scenario("failed_logins")
def failed_logins_scenario(server_id: str | None = None) -> dict[str, Any]:
    return demo_auth_spike()


@scenario("recovery")
def recovery(server_id: str | None = None) -> dict[str, Any]:
    if server_id:
        return recover_single_server(server_id)
    return demo_normal()


def inject_scenario(name: str, server_id: str | None = None) -> dict[str, Any]:
    fn = get_scenario(name)
    if fn is None:
        return {"status": "error", "message": f"Scenario '{name}' not found", "available": list_scenarios()}
    try:
        if server_id:
            return fn(server_id=server_id)
        return fn()
    except TypeError:
        return fn()


def inject_random_scenario() -> dict[str, Any]:
    # Select from weighted scenario names
    names = list(SCENARIO_WEIGHTS.keys())
    weights = list(SCENARIO_WEIGHTS.values())
    chosen = random.choices(names, weights=weights, k=1)[0]
    return inject_scenario(chosen)
