"""
VYTRON — Server Profiles
Defines the 10 simulated infrastructure nodes with mutable runtime state,
role-specific baselines, live operational log buffers, and inter-service
dependency cascading logic.
"""

from __future__ import annotations

import copy
import logging
import random
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.constants import SERVER_PROFILES

logger = logging.getLogger("vytron.simulator.profiles")

# ── Role-Specific Realistic Baselines ─────────────────────────────────────
# Each server has tailored baselines reflecting its architecture role.

ROLE_BASELINES: dict[str, dict[str, float]] = {
    "APP-01": {
        "cpu_usage": 34.5,
        "memory_usage": 46.2,
        "disk_usage": 42.0,
        "network_upload": 180.0,    # KB/s
        "network_download": 240.0,  # KB/s
        "network_latency": 11.2,    # ms
        "request_rate": 145.0,      # req/s
        "error_rate": 0.08,         # %
        "response_time": 42.0,      # ms
        "service_availability": 1.0,
    },
    "DB-01": {
        "cpu_usage": 28.0,
        "memory_usage": 68.4,       # High buffer cache
        "disk_usage": 71.5,
        "network_upload": 410.0,
        "network_download": 290.0,
        "network_latency": 4.8,
        "request_rate": 260.0,      # queries/s
        "error_rate": 0.01,
        "response_time": 14.5,
        "service_availability": 1.0,
    },
    "AUTH-01": {
        "cpu_usage": 19.5,
        "memory_usage": 32.0,
        "disk_usage": 24.0,
        "network_upload": 75.0,
        "network_download": 82.0,
        "network_latency": 8.5,
        "request_rate": 58.0,
        "error_rate": 0.02,
        "response_time": 22.0,
        "failed_logins": 0.0,
        "service_availability": 1.0,
    },
    "WEB-01": {
        "cpu_usage": 41.2,
        "memory_usage": 36.8,
        "disk_usage": 29.5,
        "network_upload": 1450.0,
        "network_download": 2100.0,
        "network_latency": 14.2,
        "request_rate": 235.0,
        "error_rate": 0.15,
        "response_time": 32.5,
        "service_availability": 1.0,
    },
    "STORAGE-01": {
        "cpu_usage": 16.0,
        "memory_usage": 42.5,
        "disk_usage": 79.2,         # Storage intensive
        "network_upload": 820.0,
        "network_download": 910.0,
        "network_latency": 11.8,
        "request_rate": 48.0,
        "error_rate": 0.0,
        "response_time": 52.0,
        "service_availability": 1.0,
    },
    "APP-02": {
        "cpu_usage": 27.5,
        "memory_usage": 54.0,
        "disk_usage": 37.0,
        "network_upload": 95.0,
        "network_download": 115.0,
        "network_latency": 9.5,
        "request_rate": 42.0,
        "error_rate": 0.05,
        "response_time": 78.0,
        "service_availability": 1.0,
    },
    "DB-02": {
        "cpu_usage": 21.0,
        "memory_usage": 59.2,
        "disk_usage": 67.8,
        "network_upload": 160.0,
        "network_download": 310.0,
        "network_latency": 5.5,
        "request_rate": 185.0,
        "error_rate": 0.01,
        "response_time": 11.8,
        "service_availability": 1.0,
    },
    "NETWORK-01": {
        "cpu_usage": 29.0,
        "memory_usage": 24.5,
        "disk_usage": 18.0,
        "network_upload": 3800.0,
        "network_download": 4400.0,
        "network_latency": 3.6,
        "request_rate": 920.0,
        "error_rate": 0.01,
        "response_time": 2.8,
        "packet_loss": 0.02,
        "service_availability": 1.0,
    },
    "BACKUP-01": {
        "cpu_usage": 17.5,
        "memory_usage": 34.0,
        "disk_usage": 63.4,
        "network_upload": 480.0,
        "network_download": 190.0,
        "network_latency": 13.5,
        "request_rate": 14.0,
        "error_rate": 0.0,
        "response_time": 105.0,
        "service_availability": 1.0,
    },
    "INTERNAL-01": {
        "cpu_usage": 23.0,
        "memory_usage": 33.5,
        "disk_usage": 34.2,
        "network_upload": 125.0,
        "network_download": 140.0,
        "network_latency": 6.8,
        "request_rate": 78.0,
        "error_rate": 0.04,
        "response_time": 17.5,
        "service_availability": 1.0,
    },
}


# ── Server State Model ──────────────────────────────────────────────────

class ServerState:
    """
    Mutable runtime representation of a simulated server.
    Maintains independent simulation state, operational activities, and log buffer.
    """

    def __init__(self, server_id: str, profile: dict[str, str]) -> None:
        self.server_id: str = server_id
        self.name: str = profile["name"]
        self.server_type: str = profile["type"]
        self.role: str = profile.get("role", "Infrastructure node")

        # Initialise role-specific baselines
        base = ROLE_BASELINES.get(server_id, ROLE_BASELINES["APP-01"])
        self.baselines: dict[str, float] = copy.deepcopy(base)
        self.current: dict[str, float] = copy.deepcopy(base)

        # Uptime tracking (simulates days of continuous execution)
        self.uptime_base_seconds: float = random.uniform(86400 * 4, 86400 * 25)
        self.boot_timestamp: float = time.time()
        self.is_failed: bool = False

        # Metadata bag
        self.metadata: dict[str, Any] = {}

        # Live operational activity and dynamic log history (last 35 entries)
        self.activity: str = f"Operating normally: {self.role}"
        self.log_history: deque[dict[str, str]] = deque(maxlen=35)
        self.add_log("INFO", f"System bootstrap complete for {self.name}. Daemon active.")

    def add_log(self, level: str, message: str) -> None:
        """Append a timestamped operational log entry."""
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = {
            "timestamp": ts,
            "level": level.upper(),
            "server_id": self.server_id,
            "message": message,
        }
        self.log_history.append(entry)

    def get_uptime_seconds(self) -> float:
        """Calculate elapsed uptime taking failures into account."""
        if self.is_failed or self.current.get("service_availability", 1.0) <= 0:
            return 0.0
        elapsed = time.time() - self.boot_timestamp
        return round(self.uptime_base_seconds + elapsed, 1)

    def reset_to_baseline(self) -> None:
        """Restore server to pristine baseline operational state."""
        self.current = copy.deepcopy(self.baselines)
        self.is_failed = False
        self.boot_timestamp = time.time()
        self.metadata.clear()
        self.activity = f"Operating normally: {self.role}"
        self.add_log("INFO", f"System restored to normal baseline operation. Health OK.")

    def compute_health_state(self) -> str:
        """
        Calculates health badge: ONLINE, WARNING, CRITICAL, or OFFLINE.
        """
        if self.is_failed or self.current.get("service_availability", 1.0) <= 0:
            return "OFFLINE"

        cpu = self.current.get("cpu_usage", 0.0)
        mem = self.current.get("memory_usage", 0.0)
        disk = self.current.get("disk_usage", 0.0)
        err = self.current.get("error_rate", 0.0)
        lat = self.current.get("network_latency", 0.0)
        resp = self.current.get("response_time", 0.0)
        loss = self.current.get("packet_loss", 0.0)
        fails = self.current.get("failed_logins", 0.0)

        # Critical triggers
        if (
            cpu >= 90.0
            or mem >= 95.0
            or disk >= 90.0
            or err >= 15.0
            or lat >= 300.0
            or resp >= 500.0
            or loss >= 5.0
            or fails >= 10.0
        ):
            return "CRITICAL"

        # Warning triggers
        if (
            cpu >= 80.0
            or mem >= 85.0
            or disk >= 80.0
            or err >= 5.0
            or lat >= 150.0
            or resp >= 250.0
            or loss >= 3.0
            or fails >= 5.0
        ):
            return "WARNING"

        return "ONLINE"

    def snapshot(self) -> dict[str, Any]:
        """Return a complete JSON-serialisable snapshot for UI/API consumption."""
        current_data = dict(self.current)
        current_data["uptime"] = self.get_uptime_seconds()

        return {
            "server_id": self.server_id,
            "server_name": self.name,
            "server_type": self.server_type,
            "role": self.role,
            "status": self.compute_health_state(),
            "is_failed": self.is_failed,
            "activity": self.activity,
            "baselines": dict(self.baselines),
            "current": current_data,
            "metadata": dict(self.metadata),
            "recent_logs": list(self.log_history),
        }

    def __repr__(self) -> str:
        return f"<ServerState {self.server_id} [{self.compute_health_state()}]>"


# ── Dependency Cascading Engine ──────────────────────────────────────────

def apply_cascading_dependencies(servers: dict[str, ServerState]) -> None:
    """
    Evaluates real inter-service dependencies. When an upstream dependency
    degrades or crashes, it automatically cascades realistic impact
    down to dependent services.
    """
    db01 = servers.get("DB-01")
    app01 = servers.get("APP-01")
    web01 = servers.get("WEB-01")
    auth01 = servers.get("AUTH-01")
    storage01 = servers.get("STORAGE-01")
    backup01 = servers.get("BACKUP-01")
    net01 = servers.get("NETWORK-01")
    app02 = servers.get("APP-02")
    db02 = servers.get("DB-02")

    # 1. DB-01 Failure / Degradation Cascade -> APP-01 -> WEB-01
    if db01 and (db01.current.get("service_availability", 1.0) <= 0 or db01.is_failed):
        if app01 and not app01.is_failed:
            app01.current["error_rate"] = max(app01.current.get("error_rate", 0), 44.5)
            app01.current["response_time"] = max(app01.current.get("response_time", 0), 820.0)
            app01.activity = "Cascading Error: Database DB-01 connection refused on port 5432"
            app01.add_log("CRITICAL", "DB Connection Refused: postgresql://db-01:5432/vytron_prod timed out")

        if web01 and not web01.is_failed:
            web01.current["error_rate"] = max(web01.current.get("error_rate", 0), 28.0)
            web01.current["response_time"] = max(web01.current.get("response_time", 0), 650.0)
            web01.activity = "Upstream Degradation: APP-01 returning HTTP 504 Gateway Timeout"
            web01.add_log("WARNING", "Upstream cluster APP-01 latency spike: 504 Gateway Timeout")

    # 2. AUTH-01 Degradation -> APP-01
    if auth01 and (auth01.current.get("service_availability", 1.0) <= 0 or auth01.current.get("failed_logins", 0) > 10):
        if app01 and not app01.is_failed:
            app01.current["error_rate"] = max(app01.current.get("error_rate", 0), 22.0)
            app01.activity = "Auth Cascade: JWT verification queue blocked by AUTH-01"
            app01.add_log("WARNING", "JWT verification failed: AUTH-01 endpoint timed out")

    # 3. NETWORK-01 Degradation -> All Nodes
    if net01 and (net01.current.get("packet_loss", 0) >= 4.0 or net01.current.get("network_latency", 0) >= 200.0):
        lat_spike = net01.current.get("network_latency", 200.0) * 0.7
        for sid, srv in servers.items():
            if sid != "NETWORK-01" and not srv.is_failed:
                srv.current["network_latency"] = max(srv.current.get("network_latency", 0), lat_spike)
                srv.current["network_upload"] = max(10.0, srv.current.get("network_upload", 100.0) * 0.6)
                srv.current["network_download"] = max(10.0, srv.current.get("network_download", 100.0) * 0.6)
                srv.activity = "Network Throttle: Upstream packet loss and switch latency"

    # 4. STORAGE-01 Disk Pressure -> BACKUP-01
    if storage01 and (storage01.current.get("disk_usage", 0) >= 90.0 or storage01.current.get("service_availability", 1.0) <= 0):
        if backup01 and not backup01.is_failed:
            backup01.current["error_rate"] = max(backup01.current.get("error_rate", 0), 60.0)
            backup01.activity = "Backup Aborted: Target volume /mnt/storage-01 full (>90%)"
            backup01.add_log("ERROR", "IOError: Target volume STORAGE-01 has insufficient disk space")

    # 5. APP-01 Complete Outage -> WEB-01 502 Bad Gateway
    if app01 and (app01.current.get("service_availability", 1.0) <= 0 or app01.is_failed):
        if web01 and not web01.is_failed:
            web01.current["error_rate"] = max(web01.current.get("error_rate", 0), 75.0)
            web01.current["response_time"] = max(web01.current.get("response_time", 0), 1250.0)
            web01.activity = "Ingress Error: Upstream APP-01 offline (HTTP 502 Bad Gateway)"
            web01.add_log("CRITICAL", "Proxy Pass: connect() to 10.0.1.10:8000 failed (Connection Refused)")


# ── Global Registry ─────────────────────────────────────────────────────

_servers: dict[str, ServerState] = {}


def _initialise_servers() -> dict[str, ServerState]:
    """Create a ServerState for every entry in SERVER_PROFILES."""
    registry: dict[str, ServerState] = {}
    for sid, profile in SERVER_PROFILES.items():
        registry[sid] = ServerState(sid, profile)
    return registry


def get_all_servers() -> dict[str, ServerState]:
    """Return the global server registry, initialising on first call."""
    global _servers
    if not _servers:
        _servers = _initialise_servers()
    return _servers


def get_server(server_id: str) -> ServerState | None:
    """Look up a single server by ID."""
    return get_all_servers().get(server_id)


def reset_all_servers() -> None:
    """Reset every server to its baseline state."""
    for srv in get_all_servers().values():
        srv.reset_to_baseline()


def list_server_ids() -> list[str]:
    """Return a sorted list of all server IDs."""
    return sorted(get_all_servers().keys())
