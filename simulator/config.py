"""
VYTRON — Simulator Configuration
Scenario schedule config, timing intervals, and collector target settings.
All tunables are imported from shared.constants where applicable.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.constants import (
    SIMULATOR_PORT,
    COLLECTOR_URL,
    TELEMETRY_INTERVAL_SECONDS,
    SCENARIO_INJECTION_INTERVAL,
    SERVER_PROFILES,
)


# ── Network Targets ─────────────────────────────────────────────────────

COLLECTOR_TELEMETRY_ENDPOINT: str = f"{COLLECTOR_URL}/telemetry"

# ── Timing ───────────────────────────────────────────────────────────────

TELEMETRY_PUSH_INTERVAL: float = float(TELEMETRY_INTERVAL_SECONDS)   # seconds
SCENARIO_INJECT_INTERVAL: float = float(SCENARIO_INJECTION_INTERVAL)  # seconds

# ── Simulator HTTP Server ───────────────────────────────────────────────

SIMULATOR_HOST: str = "0.0.0.0"
SIMULATOR_PORT_NUM: int = SIMULATOR_PORT  # 8001

# ── Scenario Weights ────────────────────────────────────────────────────
# Relative probability weights for random scenario selection.
# Higher weight → more likely to be chosen by inject_random_scenario().

SCENARIO_WEIGHTS: dict[str, float] = {
    "cpu_spike":               1.0,
    "memory_exhaustion":       1.0,
    "disk_pressure":           0.8,
    "database_failure":        0.6,
    "service_outage":          0.6,
    "network_latency_spike":   0.9,
    "packet_loss_spike":       0.7,
    "failed_logins":           0.8,
    "recovery":                1.5,   # slightly more likely to let things heal
    "sensitive_data_injection": 0.5,
}

# Ordered list of scenario names (derived from weights for consistency)
SCENARIO_NAMES: list[str] = list(SCENARIO_WEIGHTS.keys())

# ── Scenario Duration ───────────────────────────────────────────────────
# How many telemetry cycles a non-recovery scenario persists before
# the next injection overrides it.  Not enforced automatically — the
# scenario_loop simply picks a new scenario each interval.

DEFAULT_SCENARIO_DURATION_CYCLES: int = int(
    SCENARIO_INJECT_INTERVAL / TELEMETRY_PUSH_INTERVAL
)

# ── Noise Tuning ────────────────────────────────────────────────────────
# Standard-deviation multiplier applied to gauss() noise on baselines.

NOISE_SCALE: float = 1.0

# ── HTTP Client Settings ────────────────────────────────────────────────

HTTP_TIMEOUT_SECONDS: float = 10.0
HTTP_MAX_RETRIES: int = 3

# ── Logging ──────────────────────────────────────────────────────────────

LOG_LEVEL: str = "INFO"
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
