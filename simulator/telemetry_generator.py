"""
VYTRON — Telemetry Generator
Produces realistic RawTelemetryEvent objects for all 10 servers by sampling
each metric with Gaussian noise around the server's current state values,
evaluating inter-service dependencies, and appending real operational logs.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.schemas import Category, RawTelemetryEvent
from simulator.server_profiles import (
    ServerState,
    get_all_servers,
    apply_cascading_dependencies,
)
from simulator.config import NOISE_SCALE


# ── Noise Profiles & Clamping Bounds ─────────────────────────────────────

_NOISE_PROFILES: dict[str, dict[str, Any]] = {
    "cpu_usage": {
        "std": 2.2,
        "min": 0.0,
        "max": 100.0,
    },
    "memory_usage": {
        "std": 1.5,
        "min": 0.0,
        "max": 100.0,
    },
    "disk_usage": {
        "std": 0.5,
        "min": 0.0,
        "max": 100.0,
    },
    "network_upload": {
        "std": 35.0,
        "min": 0.0,
        "max": 100000.0,
    },
    "network_download": {
        "std": 45.0,
        "min": 0.0,
        "max": 100000.0,
    },
    "network_latency": {
        "std": 1.8,
        "min": 0.5,
        "max": 5000.0,
    },
    "request_rate": {
        "std": 12.0,
        "min": 0.0,
        "max": 50000.0,
    },
    "error_rate": {
        "std": 0.08,
        "min": 0.0,
        "max": 100.0,
    },
    "response_time": {
        "std": 3.5,
        "min": 1.0,
        "max": 10000.0,
    },
    "service_availability": {
        "std": 0.0,       # binary
        "min": 0.0,
        "max": 1.0,
    },
    "failed_logins": {
        "std": 0.4,
        "min": 0.0,
        "max": 1000.0,
    },
    "packet_loss": {
        "std": 0.1,
        "min": 0.0,
        "max": 100.0,
    },
}

# ── Metric → Category Mapping ────────────────────────────────────────────

_METRIC_CATEGORY: dict[str, Category] = {
    "cpu_usage":            Category.INFRASTRUCTURE,
    "memory_usage":         Category.INFRASTRUCTURE,
    "disk_usage":           Category.INFRASTRUCTURE,
    "network_upload":       Category.NETWORK,
    "network_download":     Category.NETWORK,
    "network_latency":      Category.NETWORK,
    "packet_loss":          Category.NETWORK,
    "request_rate":         Category.APPLICATION,
    "error_rate":           Category.APPLICATION,
    "response_time":        Category.APPLICATION,
    "service_availability": Category.APPLICATION,
    "failed_logins":        Category.SECURITY,
}

# ── Metrics Per Server ───────────────────────────────────────────────────

_CORE_METRICS: list[str] = [
    "cpu_usage",
    "memory_usage",
    "disk_usage",
    "network_upload",
    "network_download",
    "network_latency",
    "request_rate",
    "error_rate",
    "response_time",
    "service_availability",
]

_ROLE_EXTRAS: dict[str, list[str]] = {
    "AUTH-01": ["failed_logins"],
    "NETWORK-01": ["packet_loss"],
}


def _metrics_for_server(server: ServerState) -> list[str]:
    """Return all metric names applicable to this server."""
    metrics = list(_CORE_METRICS)
    extras = _ROLE_EXTRAS.get(server.server_id, [])
    metrics.extend(extras)
    return metrics


# ── Dynamic Log Generation ──────────────────────────────────────────────

def _generate_dynamic_server_log(server: ServerState) -> None:
    """Generate and record a live operational log message reflecting current state."""
    sid = server.server_id
    resp = server.current.get("response_time", 25.0)
    cpu = server.current.get("cpu_usage", 30.0)
    err = server.current.get("error_rate", 0.0)
    avail = server.current.get("service_availability", 1.0)
    disk = server.current.get("disk_usage", 40.0)

    # 1. Server crashed / offline
    if avail <= 0 or server.is_failed:
        server.add_log("CRITICAL", f"FATAL: Service daemon crashed or unresponsive on {sid}. Heartbeat lost.")
        return

    # 2. Server in critical error state
    if err >= 15.0:
        server.add_log("CRITICAL", f"High error threshold breached: {err:.1f}% failure rate in processing pipeline.")
        return

    # 3. Server under high CPU pressure
    if cpu >= 85.0:
        server.add_log("WARNING", f"Thread saturation alert: CPU at {cpu:.1f}%. Throttling background executors.")
        return

    # 4. Server under disk pressure
    if disk >= 85.0:
        server.add_log("WARNING", f"Filesystem warning: Disk at {disk:.1f}% capacity. Reclaiming temp storage.")
        return

    # 5. Role-specific normal operation logs
    if sid == "APP-01":
        logs = [
            f"Handled checkout transaction /api/v1/orders in {resp:.1f}ms - 200 OK",
            f"Worker thread pool: 18 active, 32 idle, queue latency {resp*0.2:.1f}ms",
            f"Database pool connection acquired from DB-01 in 3.4ms",
            f"Synchronised user state with AUTH-01 token validator",
        ]
    elif sid == "DB-01":
        logs = [
            f"Executed query SELECT * FROM orders WHERE tenant='TENANT-01' ({resp:.1f}ms)",
            f"WAL buffer checkpoint flush completed ({round(random.uniform(1.2, 4.8), 1)} MB)",
            f"Active connection count: {int(random.uniform(25, 65))}/200. Pool healthy.",
            f"Query cache hit ratio: 94.2% across 1,840 queries",
        ]
    elif sid == "AUTH-01":
        fails = server.current.get("failed_logins", 0.0)
        if fails > 5:
            logs = [f"ALERT: Brute force detection triggered: {int(fails)} invalid passwords from remote IP"]
        else:
            logs = [
                f"Generated RS256 JWT access token for user_id={random.randint(101, 899)} in {resp:.1f}ms",
                f"OAuth2 introspection verified for incoming client session",
                f"MFA challenge confirmed via authenticator app token",
            ]
    elif sid == "WEB-01":
        logs = [
            f"HTTP GET /dashboard 200 OK ({resp:.1f}ms) - Nginx worker upstream healthy",
            f"TLS 1.3 handshake negotiated in 11ms with AES_256_GCM",
            f"Static cache hit for bundle.js (gzip 142KB). Compression ratio 3.8:1",
        ]
    elif sid == "STORAGE-01":
        logs = [
            f"Object storage block written: blob_{random.randint(100, 999)}.bin ({round(random.uniform(2.1, 7.5), 1)}MB)",
            f"IOPS throughput: {int(random.uniform(450, 850))} IOPS. Volume health OK",
            f"Scrubbing parity blocks: 0 bad sectors encountered",
        ]
    elif sid == "APP-02":
        logs = [
            f"Async job #{random.randint(4000, 9999)} completed successfully in {resp:.1f}ms",
            f"Message consumer poll: 0 pending messages in dead-letter queue",
            f"Scheduled cleanup cron cleared 84 expired session keys",
        ]
    elif sid == "DB-02":
        logs = [
            f"Binlog replication stream in sync with DB-01 (delay: {round(random.uniform(0.08, 0.35), 2)}s)",
            f"Replica read query served for reporting dashboard ({resp:.1f}ms)",
        ]
    elif sid == "NETWORK-01":
        loss = server.current.get("packet_loss", 0.0)
        if loss > 3.0:
            logs = [f"CRITICAL: Link degradation on eth0. Packet loss at {loss:.1f}%"]
        else:
            logs = [
                f"Switch ingress/egress: {int(server.current.get('request_rate', 800))} packets/s, 0 dropped",
                f"BGP route table validated: 8 internal subnets reachable",
            ]
    elif sid == "BACKUP-01":
        logs = [
            f"Scheduled snapshot integrity check: checksum verified sha256:7f4a...",
            f"Backup retention policy applied: 14 daily, 4 weekly snapshots preserved",
        ]
    else:  # INTERNAL-01
        logs = [
            f"gRPC /InternalConfig/GetSettings returned status OK in {resp:.1f}ms",
            f"Service discovery registration heartbeats verified for 10 mesh nodes",
        ]

    server.add_log("INFO", random.choice(logs))


# ── Sampling Metric with Realistic Noise ─────────────────────────────────

def _sample_metric(server: ServerState, metric: str) -> float:
    """Sample a metric value with role-tuned noise and bounds."""
    base_value: float = server.current.get(metric, 0.0)
    profile = _NOISE_PROFILES.get(metric, {"std": 1.0, "min": 0.0, "max": 100.0})

    std = profile["std"] * NOISE_SCALE

    # Binary availability
    if std == 0.0 or metric == "service_availability":
        return float(base_value)

    noisy = random.gauss(base_value, std)
    clamped = max(profile["min"], min(profile["max"], noisy))
    return round(clamped, 2)


# ── Event Generation ────────────────────────────────────────────────────

def generate_events_for_server(server: ServerState) -> list[RawTelemetryEvent]:
    """
    Generate one RawTelemetryEvent per applicable metric for *server*.
    Attaches role, activity, health state, and uptime.
    """
    now = datetime.now(timezone.utc)
    metrics = _metrics_for_server(server)
    events: list[RawTelemetryEvent] = []

    # Dynamic log emission
    _generate_dynamic_server_log(server)

    for metric in metrics:
        value = _sample_metric(server, metric)
        category = _METRIC_CATEGORY.get(metric, Category.INFRASTRUCTURE)

        meta: dict[str, Any] = {
            "server_name": server.name,
            "server_type": server.server_type,
            "role": server.role,
            "status": server.compute_health_state(),
            "activity": server.activity,
            "uptime_seconds": server.get_uptime_seconds(),
        }
        if server.metadata:
            meta.update(server.metadata)

        event = RawTelemetryEvent(
            source_id=server.server_id,
            timestamp=now,
            metric=metric,
            value=value,
            category=category,
            metadata=meta,
            event_type="metric",
        )
        events.append(event)

    return events


def generate_all_telemetry() -> list[RawTelemetryEvent]:
    """
    Applies dependency cascade across all 10 servers, then generates
    telemetry events for every server.
    """
    servers = get_all_servers()

    # Apply inter-service cascading logic before sampling
    apply_cascading_dependencies(servers)

    all_events: list[RawTelemetryEvent] = []
    for server in servers.values():
        server_events = generate_events_for_server(server)
        all_events.extend(server_events)

    return all_events
