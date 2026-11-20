"""
VYTRON — Threshold-Based Detection Engine
Evaluates telemetry metrics against warning and critical thresholds.
Implements consecutive reading confirmation to prevent false positives from transient noise.
"""

from typing import Any
from server.config import SERVERS_CONFIG

# Metric impact classification for Severity / Priority assignment
# Critical breach of TIER_1 -> CRITICAL (P1)
# Critical breach of TIER_2 -> HIGH (P2)
# Warning breach of TIER_1  -> MEDIUM (P3)
# Warning breach of TIER_2  -> LOW (P4)
TIER_1_METRICS = {
    "APP-01.cpu_utilization",
    "APP-01.response_time",
    "DB-01.query_latency",
    "DB-01.active_connections",
    "AUTH-01.auth_success_rate",
    "AUTH-01.failed_login_attempts",
    "BACKUP-01.backup_failure_count",
    "NETWORK-01.packet_loss",
    "NETWORK-01.network_latency",
}

class ThresholdDetector:
    def __init__(self, consecutive_required: int = 2):
        self.consecutive_required = consecutive_required
        # Tracks consecutive breach count: (server_id, param_key) -> int
        self.breach_counts: dict[str, int] = {}
        # Tracks consecutive normal count: (server_id, param_key) -> int
        self.normal_counts: dict[str, int] = {}
        # Tracks last detected breach level: (server_id, param_key) -> "critical" | "warning" | None
        self.active_breach_levels: dict[str, str | None] = {}

    def evaluate_server(
        self, server_id: str, current_metrics: dict[str, float]
    ) -> tuple[str, list[dict[str, Any]], list[str]]:
        """
        Evaluates 4 parameters of a server.
        Returns:
            - server_status: "CRITICAL" | "WARNING" | "NORMAL"
            - confirmed_breaches: list of breach details confirmed by consecutive evaluation
            - confirmed_recoveries: list of param_keys that have confirmed recovery back to normal
        """
        server_conf = SERVERS_CONFIG.get(server_id)
        if not server_conf:
            return "NORMAL", [], []

        confirmed_breaches = []
        confirmed_recoveries = []
        param_statuses = []

        params_conf = server_conf["parameters"]

        for param_key, conf in params_conf.items():
            thresholds = conf.get("thresholds")
            if not thresholds:
                param_statuses.append("NORMAL")
                continue

            val = current_metrics.get(param_key)
            if val is None:
                continue

            direction = thresholds.get("direction", "above")
            warn_val = thresholds.get("warning")
            crit_val = thresholds.get("critical")

            # Check threshold breach
            is_crit = False
            is_warn = False

            if direction == "above":
                if crit_val is not None and val >= crit_val:
                    is_crit = True
                elif warn_val is not None and val >= warn_val:
                    is_warn = True
            elif direction == "below":
                if crit_val is not None and val <= crit_val:
                    is_crit = True
                elif warn_val is not None and val <= warn_val:
                    is_warn = True

            state_key = f"{server_id}.{param_key}"

            if is_crit or is_warn:
                breach_type = "critical" if is_crit else "warning"
                thresh_used = crit_val if is_crit else warn_val

                self.breach_counts[state_key] = self.breach_counts.get(state_key, 0) + 1
                self.normal_counts[state_key] = 0

                # Only confirm after reaching consecutive_required
                if self.breach_counts[state_key] >= self.consecutive_required:
                    self.active_breach_levels[state_key] = breach_type
                    param_statuses.append("CRITICAL" if is_crit else "WARNING")

                    # Severity and Priority mapping
                    is_tier_1 = state_key in TIER_1_METRICS
                    if is_crit:
                        severity = "CRITICAL" if is_tier_1 else "HIGH"
                        priority = "P1" if is_tier_1 else "P2"
                    else:
                        severity = "MEDIUM" if is_tier_1 else "LOW"
                        priority = "P3" if is_tier_1 else "P4"

                    confirmed_breaches.append({
                        "server_id": server_id,
                        "server_name": server_conf["name"],
                        "server_type": server_conf["type"],
                        "metric_key": param_key,
                        "metric_name": conf["name"],
                        "observed_value": round(val, 2),
                        "threshold_value": round(thresh_used, 2),
                        "unit": conf["unit"],
                        "breach_level": breach_type,
                        "severity": severity,
                        "priority": priority,
                        "direction": direction,
                    })
                else:
                    # Still in evaluation window; preserve previous status if any
                    prev = self.active_breach_levels.get(state_key)
                    param_statuses.append("CRITICAL" if prev == "critical" else ("WARNING" if prev == "warning" else "NORMAL"))
            else:
                # Value is within normal baseline
                self.normal_counts[state_key] = self.normal_counts.get(state_key, 0) + 1
                if self.normal_counts[state_key] >= self.consecutive_required:
                    self.breach_counts[state_key] = 0
                    if self.active_breach_levels.get(state_key) is not None:
                        self.active_breach_levels[state_key] = None
                        confirmed_recoveries.append(param_key)
                    param_statuses.append("NORMAL")
                else:
                    # Preserving state until normal confirmation window met
                    prev = self.active_breach_levels.get(state_key)
                    param_statuses.append("CRITICAL" if prev == "critical" else ("WARNING" if prev == "warning" else "NORMAL"))

        # Determine overall server status
        if "CRITICAL" in param_statuses:
            overall_status = "CRITICAL"
        elif "WARNING" in param_statuses:
            overall_status = "WARNING"
        else:
            overall_status = "NORMAL"

        return overall_status, confirmed_breaches, confirmed_recoveries

    def reset(self):
        """Reset all counters and breach states."""
        self.breach_counts.clear()
        self.normal_counts.clear()
        self.active_breach_levels.clear()
