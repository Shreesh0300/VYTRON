"""
CICADA AIOps — Server Profiles
Defines the 10 simulated infrastructure nodes with mutable runtime state
and immutable baseline definitions.  Every server exposes a state dict
that scenarios can mutate; the telemetry generator reads from that state.
"""

from __future__ import annotations

import copy
import random
from typing import Any

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.constants import SERVER_PROFILES


# ── Baseline Ranges ──────────────────────────────────────────────────────
# Each tuple is (low, high) used to seed the initial baseline value.

_BASELINE_RANGES: dict[str, tuple[float, float]] = {
    "cpu_usage":            (20.0, 40.0),
    "memory_usage":         (30.0, 50.0),
    "disk_usage":           (40.0, 60.0),
    "network_latency":      (5.0, 20.0),
    "packet_loss":          (0.0, 0.5),
    "service_availability": (1.0, 1.0),
    "failed_logins":        (0.0, 0.0),
}


def _random_baseline(metric: str) -> float:
    """Return a random baseline within the defined range for *metric*."""
    low, high = _BASELINE_RANGES[metric]
    return round(random.uniform(low, high), 2)


# ── Server State Model ──────────────────────────────────────────────────

class ServerState:
    """
    Mutable runtime representation of a single simulated server.

    Attributes
    ----------
    server_id : str          – e.g. "APP-01"
    name : str               – human-readable label
    server_type : str        – from SERVER_PROFILES type field
    baselines : dict         – original metric baselines (immutable reference)
    current : dict           – live metric values (mutated by scenarios)
    metadata : dict          – arbitrary metadata attached to emitted events
    """

    def __init__(self, server_id: str, profile: dict[str, str]) -> None:
        self.server_id: str = server_id
        self.name: str = profile["name"]
        self.server_type: str = profile["type"]

        # Generate random baselines within the prescribed ranges
        self.baselines: dict[str, float] = {
            metric: _random_baseline(metric) for metric in _BASELINE_RANGES
        }

        # Current state starts as a copy of baselines
        self.current: dict[str, float] = copy.deepcopy(self.baselines)

        # Metadata bag — scenarios may inject extra k/v pairs here
        self.metadata: dict[str, Any] = {}

    # ── convenience ──────────────────────────────────────────────────

    def reset_to_baseline(self) -> None:
        """Restore every metric to its original baseline value and clear metadata."""
        self.current = copy.deepcopy(self.baselines)
        self.metadata.clear()

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of this server's state."""
        return {
            "server_id": self.server_id,
            "name": self.name,
            "type": self.server_type,
            "baselines": dict(self.baselines),
            "current": dict(self.current),
            "metadata": dict(self.metadata),
        }

    def __repr__(self) -> str:
        return f"<ServerState {self.server_id} ({self.server_type})>"


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
    """Look up a single server by ID.  Returns None if not found."""
    return get_all_servers().get(server_id)


def reset_all_servers() -> None:
    """Reset every server to its baseline state."""
    for srv in get_all_servers().values():
        srv.reset_to_baseline()


def list_server_ids() -> list[str]:
    """Return a sorted list of all server IDs."""
    return sorted(get_all_servers().keys())
