"""
CICADA AIOps — Telemetry Generator
Produces realistic RawTelemetryEvent objects for every server by sampling
each metric with Gaussian noise around the server's current state values.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.schemas import Category, RawTelemetryEvent
from simulator.server_profiles import ServerState, get_all_servers
from simulator.config import NOISE_SCALE


# ── Noise Profiles ──────────────────────────────────────────────────────
# Maps each metric to its standard deviation for gauss() noise and
# optional clamping bounds (min, max).

_NOISE_PROFILES: dict[str, dict[str, Any]] = {
    "cpu_usage": {
        "std": 3.0,
        "min": 0.0,
        "max": 100.0,
    },
    "memory_usage": {
        "std": 2.5,
        "min": 0.0,
        "max": 100.0,
    },
    "disk_usage": {
        "std": 1.0,
        "min": 0.0,
        "max": 100.0,
    },
    "network_latency": {
        "std": 2.0,
        "min": 0.5,
        "max": 10000.0,
    },
    "packet_loss": {
        "std": 0.1,
        "min": 0.0,
        "max": 100.0,
    },
    "service_availability": {
        "std": 0.0,       # binary — no noise by default
        "min": 0.0,
        "max": 1.0,
    },
    "failed_logins": {
        "std": 0.5,
        "min": 0.0,
        "max": 1000.0,
    },
}

# ── Metric → Category mapping ───────────────────────────────────────────

_METRIC_CATEGORY: dict[str, Category] = {
    "cpu_usage":            Category.INFRASTRUCTURE,
    "memory_usage":         Category.INFRASTRUCTURE,
    "disk_usage":           Category.INFRASTRUCTURE,
    "network_latency":      Category.NETWORK,
    "packet_loss":          Category.NETWORK,
    "service_availability": Category.APPLICATION,
    "failed_logins":        Category.SECURITY,
}

# ── Server-type → applicable metrics ────────────────────────────────────
# Every server gets infrastructure + network metrics; some get extras.

_BASE_METRICS: list[str] = [
    "cpu_usage",
    "memory_usage",
    "disk_usage",
    "network_latency",
    "packet_loss",
    "service_availability",
]

_EXTRA_METRICS_BY_TYPE: dict[str, list[str]] = {
    "authentication": ["failed_logins"],
}


def _metrics_for_server(server: ServerState) -> list[str]:
    """Return the list of metric names applicable to *server*."""
    metrics = list(_BASE_METRICS)
    extras = _EXTRA_METRICS_BY_TYPE.get(server.server_type, [])
    metrics.extend(extras)
    return metrics


# ── Noisy Sampling ──────────────────────────────────────────────────────

def _sample_metric(server: ServerState, metric: str) -> float:
    """
    Sample a metric value for *server* with Gaussian noise around its
    current state value, clamped to the metric's valid range.
    """
    base_value: float = server.current.get(metric, 0.0)
    profile = _NOISE_PROFILES.get(metric, {"std": 1.0, "min": 0.0, "max": 100.0})

    std = profile["std"] * NOISE_SCALE

    # For binary metrics (availability) with zero std, return exact value
    if std == 0.0:
        return base_value

    noisy = random.gauss(base_value, std)
    clamped = max(profile["min"], min(profile["max"], noisy))
    return round(clamped, 2)


# ── Event Generation ────────────────────────────────────────────────────

def generate_events_for_server(server: ServerState) -> list[RawTelemetryEvent]:
    """
    Generate one RawTelemetryEvent per applicable metric for *server*.
    Returns a list of events with a shared UTC timestamp.
    """
    now = datetime.now(timezone.utc)
    metrics = _metrics_for_server(server)
    events: list[RawTelemetryEvent] = []

    for metric in metrics:
        value = _sample_metric(server, metric)
        category = _METRIC_CATEGORY.get(metric, Category.INFRASTRUCTURE)

        # Build metadata — always include server type; merge any scenario metadata
        meta: dict[str, Any] = {
            "server_name": server.name,
            "server_type": server.server_type,
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
    Generate telemetry events for every registered server.
    Returns a flat list of RawTelemetryEvent objects.
    """
    all_events: list[RawTelemetryEvent] = []
    servers = get_all_servers()

    for server in servers.values():
        server_events = generate_events_for_server(server)
        all_events.extend(server_events)

    return all_events
